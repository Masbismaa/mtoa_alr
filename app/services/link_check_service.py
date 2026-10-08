"""Pemeriksaan manual dari worker/CLI, dengan validasi target dan IP yang dikunci."""
import http.client
import socket
import ssl
from collections import Counter, namedtuple
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from functools import partial
from urllib.parse import urljoin
from flask import current_app
from app.extensions import db
from app.models import AccessEntry
from app.security.link_target_guard import LinkTargetBlockedError, parse_check_url, resolve_safe_ip
from app.utils.constants import (
    LINK_CHECK_MAX_REDIRECT_COUNT,
    LINK_CHECK_MAX_WORKER_COUNT,
    LINK_CHECK_TARGET_DEADLINE_SECONDS,
    LINK_CHECK_TIMEOUT_SECONDS,
    LINK_CHECK_USER_AGENT,
    LINK_STATUS_DOWN,
    LINK_STATUS_NOTE_MAX_LENGTH,
    LINK_STATUS_UNKNOWN,
    LINK_STATUS_UP,
)
from app.utils.datetime_helper import utc_now

# hasil satu kali cek: status (up/down/unknown) + alasannya
LinkCheckResult = namedtuple("LinkCheckResult", ["status", "note"])

# yg mau dicek dari satu link, dipisah dari objek ORM biar aman dipake di thread
LinkCheckTarget = namedtuple("LinkCheckTarget", ["entry_id", "url", "address", "port"])

REDIRECT_STATUS_SET = {301, 302, 303, 307, 308}
# banyaknya link yg dibaca dari DB sekali ambil (pemeriksaannya sendiri jalan terus, ga per kelompok)
CHECK_BATCH_SIZE = 20

class PinnedHTTPConnection(http.client.HTTPConnection):
    """Koneksi HTTP ke IP yg udah lolos satpam. Header Host tetep pake nama aslinya."""

    def __init__(self, hostname, pinned_ip, port, timeout):
        super().__init__(hostname, port, timeout=timeout)
        self.pinned_ip = pinned_ip

    def connect(self):
        """Konek ke IP yg dikunci, bukan resolve DNS ulang."""
        self.sock = socket.create_connection((self.pinned_ip, self.port), self.timeout)

class PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Koneksi HTTPS ke IP yg udah lolos satpam. Sertifikat tetep dicek pake nama host aslinya."""

    def __init__(self, hostname, pinned_ip, port, timeout, ssl_context):
        super().__init__(hostname, port, timeout=timeout, context=ssl_context)
        self.pinned_ip = pinned_ip

    def connect(self):
        """Konek ke IP yg dikunci, terus bungkus SSL pake nama host asli (SNI)."""
        raw_socket = socket.create_connection((self.pinned_ip, self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)
        except Exception:
            raw_socket.close()
            raise

def build_check_target(entry):
    """Ambil data yg perlu dicek aja dari satu link."""
    return LinkCheckTarget(entry.id, entry.url, entry.address, entry.port)

def describe_connection_error(error):
    """Error koneksi jadi teks yg gampang dibaca."""
    if isinstance(error, TimeoutError):
        return f"Timeout (lebih dari {LINK_CHECK_TIMEOUT_SECONDS} detik)"
    if isinstance(error, ConnectionRefusedError):
        return "Koneksi ditolak"
    if isinstance(error, socket.gaierror):
        return "Alamat tidak ditemukan"
    if isinstance(error, ssl.SSLError):
        return "Error SSL"
    return "Tidak bisa terhubung"

def send_request(parsed_url, pinned_ip, ssl_context):
    """Kirim GET sekali (redirect ga diikutin otomatis). Balikin (kode HTTP, header Location)."""
    if parsed_url.scheme == "https":
        connection = PinnedHTTPSConnection(parsed_url.hostname, pinned_ip, parsed_url.port, LINK_CHECK_TIMEOUT_SECONDS, ssl_context)
    else:
        connection = PinnedHTTPConnection(parsed_url.hostname, pinned_ip, parsed_url.port, LINK_CHECK_TIMEOUT_SECONDS)
    try:
        connection.request("GET", parsed_url.request_path, headers={"User-Agent": LINK_CHECK_USER_AGENT})
        response = connection.getresponse()
        return response.status, response.getheader("Location")
    finally:
        connection.close()

def open_checked_url(parsed_url, pinned_ip, ca_file=None):
    """Sertifikat selalu diverifikasi; CA kantor dapat disediakan oleh operator."""
    return send_request(parsed_url, pinned_ip, ssl.create_default_context(cafile=ca_file)), ""

def build_http_result(status_code, note_suffix=""):
    """Server ngejawab di bawah 500 (termasuk 401/403 halaman login) dianggap aktif."""
    status = LINK_STATUS_UP if status_code < 500 else LINK_STATUS_DOWN
    return LinkCheckResult(status, f"HTTP {status_code}{note_suffix}")

def follow_url(url, allow_private=None, ca_file=None):
    """Cek URL + ikutin redirect maksimal 3x, tiap tujuan redirect dicek dulu sebelum dikoneksi."""
    parsed_url = parse_check_url(url)
    pinned_ip = resolve_safe_ip(parsed_url.hostname, parsed_url.port, allow_private)
    current_url = url
    note_suffix = ""
    for redirect_count in range(LINK_CHECK_MAX_REDIRECT_COUNT + 1):
        (status_code, location), cert_note = open_checked_url(parsed_url, pinned_ip, ca_file)
        note_suffix = note_suffix or cert_note
        if status_code not in REDIRECT_STATUS_SET or not location:
            return build_http_result(status_code, note_suffix)
        if redirect_count == LINK_CHECK_MAX_REDIRECT_COUNT:
            break
        next_url = urljoin(current_url, location)
        try:
            parsed_url = parse_check_url(next_url)
            pinned_ip = resolve_safe_ip(parsed_url.hostname, parsed_url.port, allow_private)
        except (LinkTargetBlockedError, OSError):
            # server asal tetep hidup, cuma tujuan redirect-nya ga boleh didatengin
            return build_http_result(status_code, " · redirect ke alamat terlarang tidak diikuti")
        current_url = next_url
    return build_http_result(status_code, f" · redirect lebih dari {LINK_CHECK_MAX_REDIRECT_COUNT}x, berhenti")

def check_url(url, allow_private=None, ca_file=None):
    """Cek URL. Alamat terlarang -> Belum dicek + alasannya, gagal konek -> Tidak aktif."""
    try:
        return follow_url(url, allow_private, ca_file)
    except LinkTargetBlockedError as error:
        return LinkCheckResult(LINK_STATUS_UNKNOWN, f"Diblokir: {error}")
    except (OSError, http.client.HTTPException) as error:
        return LinkCheckResult(LINK_STATUS_DOWN, describe_connection_error(error))

def check_port(address, port, allow_private=None):
    """Cek Address + Port: port kebuka berarti aktif."""
    try:
        pinned_ip = resolve_safe_ip(address, port, allow_private)
        with socket.create_connection((pinned_ip, port), timeout=LINK_CHECK_TIMEOUT_SECONDS):
            pass
    except LinkTargetBlockedError as error:
        return LinkCheckResult(LINK_STATUS_UNKNOWN, f"Diblokir: {error}")
    except OSError as error:
        return LinkCheckResult(LINK_STATUS_DOWN, describe_connection_error(error))
    return LinkCheckResult(LINK_STATUS_UP, f"Port {port} terbuka")

def check_target(target, allow_private=None, ca_file=None):
    """Pilih cara cek: URL dulu, kalau ga ada baru Address + Port. Sengaja ga pake ping (rawan command injection)."""
    if target.url:
        return check_url(target.url, allow_private, ca_file)
    if target.address and target.port:
        return check_port(target.address, target.port, allow_private)
    if target.address:
        return LinkCheckResult(LINK_STATUS_UNKNOWN, "Port kosong, tidak bisa dicek")
    return LinkCheckResult(LINK_STATUS_UNKNOWN, "Tidak ada URL atau Address")

def save_check_result(target, result):
    """Simpen hasil cek. updated_at sengaja ga ikut berubah, soalnya ngecek bukan ngedit data.
    Cuma disimpen kalau URL/Address/Port di DB masih sama kayak yg tadi dicek: kalau link-nya diedit pas
    pengecekan lagi jalan, hasil buat alamat lama ga boleh nempel ke alamat baru. Return True kalau kesimpen."""
    update_result = db.session.execute(
        db.update(AccessEntry)
        .where(
            AccessEntry.id == target.entry_id,
            # IS NOT DISTINCT FROM: NULL dianggap sama dgn NULL (kolom address/port boleh kosong)
            AccessEntry.url.is_not_distinct_from(target.url),
            AccessEntry.address.is_not_distinct_from(target.address),
            AccessEntry.port.is_not_distinct_from(target.port),
        )
        .values(
            status=result.status,
            status_note=result.note[:LINK_STATUS_NOTE_MAX_LENGTH],
            status_checked_at=utc_now(),
            updated_at=AccessEntry.updated_at,
        )
    )
    return update_result.rowcount == 1

def iter_check_target(upper_id):
    """Ambil link yg mau dicek dari DB sedikit-sedikit (per CHECK_BATCH_SIZE), transaksi langsung ditutup
    biar ga nahan DB selama nunggu jaringan. Jalan di thread utama (session DB ga boleh dipake thread pemeriksa)."""
    last_id = 0
    while True:
        rows = db.session.execute(
            db.select(AccessEntry.id, AccessEntry.url, AccessEntry.address, AccessEntry.port)
            .where(AccessEntry.id > last_id, AccessEntry.id <= upper_id)
            .order_by(AccessEntry.id).limit(CHECK_BATCH_SIZE)
        ).all()
        db.session.commit()
        if not rows:
            return
        for row in rows:
            yield LinkCheckTarget(*row)
        last_id = rows[-1].id

def read_future_result(future, target):
    """Hasil 1 pemeriksaan. Error tak terduga di 1 link ga boleh ngegagalin pemeriksaan semua link."""
    try:
        return future.result()
    except Exception:  # noqa: BLE001
        current_app.logger.exception("Pemeriksaan link id=%s error tak terduga", target.entry_id)
        return LinkCheckResult(LINK_STATUS_UNKNOWN, "Error saat memeriksa, lihat log server")

def save_result_list(result_pair_list, counts, total, progress_callback):
    """Simpen hasil yg udah kelar + update progres. Callback dicek dulu sebelum nulis: kalau kepemilikan
    pemeriksaan udah dicabut (recover-link-monitor), callback lempar error & hasil worker lama ga ditulis."""
    if progress_callback:
        progress_callback(sum(counts.values()), total)
    for target, result in result_pair_list:
        save_check_result(target, result)
        counts[result.status] += 1
    if progress_callback:
        progress_callback(sum(counts.values()), total)
    db.session.commit()

def check_all_entry_status(max_worker_count=LINK_CHECK_MAX_WORKER_COUNT, progress_callback=None):
    """Cek semua link. Pemeriksa jalan terus: begitu 1 link kelar, slot-nya langsung ngambil link berikutnya
    (ga nungguin link lain yg lebih lambat), dan hasilnya langsung disimpen.

    Tiap link dibatesin LINK_CHECK_TARGET_DEADLINE_SECONDS sejak mulai dicek. Timeout socket cuma ngebatesin
    tiap operasi (DNS yg macet / server yg ngirim data dikit-dikit bisa nahan selamanya), jadi yg lewat batas
    dianggap tidak aktif. Thread yg macet ga bisa dihentiin paksa: pool-nya ditinggal & link berikutnya pake
    pool baru, biar kapasitas pemeriksa ga berkurang."""
    upper_id = db.session.scalar(db.select(db.func.max(AccessEntry.id))) or 0
    total = db.session.scalar(db.select(db.func.count(AccessEntry.id)).where(AccessEntry.id <= upper_id))
    check = partial(check_target, allow_private=current_app.config["LINK_CHECK_ALLOW_PRIVATE_NETWORKS"],
                    ca_file=current_app.config["LINK_CHECK_CA_FILE"])
    counts = Counter()
    if progress_callback:
        progress_callback(0, total)
    db.session.commit()
    target_iter = iter_check_target(upper_id)
    executor = ThreadPoolExecutor(max_workers=max_worker_count)
    # future -> (target, batas waktu). Jumlahnya ga pernah lebih dari max_worker_count, jadi tiap link yg
    # dikirim ke pool langsung mulai dicek (batas waktunya ga kepotong antrean)
    in_flight_dict = {}
    try:
        while True:
            while len(in_flight_dict) < max_worker_count:
                target = next(target_iter, None)
                if target is None:
                    break
                future = executor.submit(check, target)
                in_flight_dict[future] = (target, time.monotonic() + LINK_CHECK_TARGET_DEADLINE_SECONDS)
            if not in_flight_dict:
                break
            nearest_deadline = min(deadline for _, deadline in in_flight_dict.values())
            done_set, _ = wait(in_flight_dict, timeout=max(0, nearest_deadline - time.monotonic()),
                               return_when=FIRST_COMPLETED)
            result_pair_list = []
            for future in done_set:
                target, _ = in_flight_dict.pop(future)
                result_pair_list.append((target, read_future_result(future, target)))
            now = time.monotonic()
            expired_list = [future for future, (_, deadline) in in_flight_dict.items() if deadline <= now]
            for future in expired_list:
                target, _ = in_flight_dict.pop(future)
                result_pair_list.append((target, LinkCheckResult(
                    LINK_STATUS_DOWN, f"Pemeriksaan melebihi {LINK_CHECK_TARGET_DEADLINE_SECONDS} detik")))
            if expired_list:
                # link yg masih jalan normal di pool lama tetep ditungguin, link baru masuk pool baru
                executor.shutdown(wait=False)
                executor = ThreadPoolExecutor(max_workers=max_worker_count)
            if result_pair_list:
                save_result_list(result_pair_list, counts, total, progress_callback)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    return counts
