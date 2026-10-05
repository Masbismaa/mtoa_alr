"""Cek status link otomatis (lewat command terjadwal). Alamat berbahaya ditolak, koneksi dikunci ke IP yg udah dicek."""
import http.client
import socket
import ssl
from collections import Counter, namedtuple
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
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
        self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)

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

def build_unverified_ssl_context():
    """Konteks SSL tanpa cek sertifikat, cuma buat ngetes server-nya hidup (ga ada data yg dikirim)."""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context

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

def open_checked_url(parsed_url, pinned_ip):
    """Request ke URL. Sertifikat self-signed dicoba ulang tanpa cek sertifikat + dikasih catatan."""
    try:
        return send_request(parsed_url, pinned_ip, ssl.create_default_context()), ""
    except ssl.SSLCertVerificationError:
        return send_request(parsed_url, pinned_ip, build_unverified_ssl_context()), " · Sertifikat SSL tidak valid"

def build_http_result(status_code, note_suffix=""):
    """Server ngejawab di bawah 500 (termasuk 401/403 halaman login) dianggap aktif."""
    status = LINK_STATUS_UP if status_code < 500 else LINK_STATUS_DOWN
    return LinkCheckResult(status, f"HTTP {status_code}{note_suffix}")

def follow_url(url):
    """Cek URL + ikutin redirect maksimal 3x, tiap tujuan redirect dicek dulu sebelum dikoneksi."""
    parsed_url = parse_check_url(url)
    pinned_ip = resolve_safe_ip(parsed_url.hostname, parsed_url.port)
    current_url = url
    note_suffix = ""
    for redirect_count in range(LINK_CHECK_MAX_REDIRECT_COUNT + 1):
        (status_code, location), cert_note = open_checked_url(parsed_url, pinned_ip)
        note_suffix = note_suffix or cert_note
        if status_code not in REDIRECT_STATUS_SET or not location:
            return build_http_result(status_code, note_suffix)
        if redirect_count == LINK_CHECK_MAX_REDIRECT_COUNT:
            break
        next_url = urljoin(current_url, location)
        try:
            parsed_url = parse_check_url(next_url)
            pinned_ip = resolve_safe_ip(parsed_url.hostname, parsed_url.port)
        except (LinkTargetBlockedError, OSError):
            # server asal tetep hidup, cuma tujuan redirect-nya ga boleh didatengin
            return build_http_result(status_code, " · redirect ke alamat terlarang tidak diikuti")
        current_url = next_url
    return build_http_result(status_code, f" · redirect lebih dari {LINK_CHECK_MAX_REDIRECT_COUNT}x, berhenti")

def check_url(url):
    """Cek URL. Alamat terlarang -> Belum dicek + alasannya, gagal konek -> Tidak aktif."""
    try:
        return follow_url(url)
    except LinkTargetBlockedError as error:
        return LinkCheckResult(LINK_STATUS_UNKNOWN, f"Diblokir: {error}")
    except (OSError, http.client.HTTPException) as error:
        return LinkCheckResult(LINK_STATUS_DOWN, describe_connection_error(error))

def check_port(address, port):
    """Cek Address + Port: port kebuka berarti aktif."""
    try:
        pinned_ip = resolve_safe_ip(address, port)
        with socket.create_connection((pinned_ip, port), timeout=LINK_CHECK_TIMEOUT_SECONDS):
            pass
    except LinkTargetBlockedError as error:
        return LinkCheckResult(LINK_STATUS_UNKNOWN, f"Diblokir: {error}")
    except OSError as error:
        return LinkCheckResult(LINK_STATUS_DOWN, describe_connection_error(error))
    return LinkCheckResult(LINK_STATUS_UP, f"Port {port} terbuka")

def check_target(target):
    """Pilih cara cek: URL dulu, kalau ga ada baru Address + Port. Sengaja ga pake ping (rawan command injection)."""
    if target.url:
        return check_url(target.url)
    if target.address and target.port:
        return check_port(target.address, target.port)
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

def check_all_entry_status(max_worker_count=LINK_CHECK_MAX_WORKER_COUNT):
    """Cek semua link (dipanggil command terjadwal). Ngeceknya paralel, nyimpennya satu-satu. Return Counter per status."""
    entry_list = db.session.execute(db.select(AccessEntry).order_by(AccessEntry.id)).scalars().all()
    target_list = [build_check_target(entry) for entry in entry_list]
    with ThreadPoolExecutor(max_workers=max_worker_count) as executor:
        result_list = list(executor.map(check_target, target_list))
    for target, result in zip(target_list, result_list):
        save_check_result(target.entry_id, result)
    db.session.commit()
    return Counter(result.status for result in result_list)