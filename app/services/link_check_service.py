"""Pemeriksaan manual dari worker/CLI, dengan validasi target dan IP yang dikunci."""
import http.client
import socket
import ssl
from collections import Counter, namedtuple
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from urllib.parse import urljoin
from flask import current_app
from app.extensions import db
from app.models import AccessEntry
from app.security.link_target_guard import LinkTargetBlockedError, parse_check_url, resolve_safe_ip
from app.utils.constants import (
    LINK_CHECK_MAX_REDIRECT_COUNT,
    LINK_CHECK_MAX_WORKER_COUNT,
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

def save_check_result(entry_id, result):
    """Simpen hasil cek. updated_at sengaja ga ikut berubah, soalnya ngecek bukan ngedit data."""
    db.session.execute(
        db.update(AccessEntry)
        .where(AccessEntry.id == entry_id)
        .values(
            status=result.status,
            status_note=result.note[:LINK_STATUS_NOTE_MAX_LENGTH],
            status_checked_at=utc_now(),
            updated_at=AccessEntry.updated_at,
        )
    )

def check_all_entry_status(max_worker_count=LINK_CHECK_MAX_WORKER_COUNT, progress_callback=None):
    """Baca snapshot dalam batch kecil, tanpa menahan transaksi selama koneksi jaringan."""
    upper_id = db.session.scalar(db.select(db.func.max(AccessEntry.id))) or 0
    total = db.session.scalar(db.select(db.func.count(AccessEntry.id)).where(AccessEntry.id <= upper_id))
    check = partial(check_target, allow_private=current_app.config["LINK_CHECK_ALLOW_PRIVATE_NETWORKS"],
                    ca_file=current_app.config["LINK_CHECK_CA_FILE"])
    counts = Counter()
    last_id = 0
    if progress_callback:
        progress_callback(0, total)
    db.session.commit()
    with ThreadPoolExecutor(max_workers=max_worker_count) as executor:
        while True:
            rows = db.session.execute(
                db.select(AccessEntry.id, AccessEntry.url, AccessEntry.address, AccessEntry.port)
                .where(AccessEntry.id > last_id, AccessEntry.id <= upper_id)
                .order_by(AccessEntry.id).limit(20)
            ).all()
            db.session.commit()
            if not rows:
                break
            targets = [LinkCheckTarget(*row) for row in rows]
            results = list(executor.map(check, targets))
            # Callback dapat menolak hasil worker yang kepemilikannya sudah dicabut.
            if progress_callback:
                progress_callback(sum(counts.values()), total)
            for target, result in zip(targets, results):
                save_check_result(target.entry_id, result)
                counts[result.status] += 1
            if progress_callback:
                progress_callback(sum(counts.values()), total)
            db.session.commit()
            last_id = rows[-1].id
    return counts
