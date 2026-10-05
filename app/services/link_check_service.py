"""Cek status link: URL dicek pake request HTTP, Address + Port dicek dengan buka koneksi ke port-nya."""
import socket
import ssl
from collections import Counter, namedtuple
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener
from app.extensions import db
from app.models import AccessEntry
from app.utils.constants import (
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

def build_check_target(entry):
    """Ambil data yg perlu dicek aja dari satu link."""
    return LinkCheckTarget(entry.id, entry.url, entry.address, entry.port)

def describe_connection_error(error):
    """Error koneksi jadi teks yg gampang dibaca user."""
    reason = getattr(error, "reason", error)
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return f"Timeout (lebih dari {LINK_CHECK_TIMEOUT_SECONDS} detik)"
    if isinstance(reason, ConnectionRefusedError):
        return "Koneksi ditolak"
    if isinstance(reason, socket.gaierror):
        return "Alamat tidak ditemukan"
    if isinstance(reason, ssl.SSLError):
        return "Error SSL"
    return "Tidak bisa terhubung"

def is_cert_error(error):
    """True kalau gagalnya cuma gara-gara sertifikat SSL ga valid (biasa di server internal / self-signed)."""
    return isinstance(getattr(error, "reason", error), ssl.SSLCertVerificationError)

def open_url(url, ssl_context):
    """Buka URL, balikin kode HTTP-nya. Body ga dibaca biar cepet. Proxy sengaja dimatiin, link ICT kebanyakan server internal."""
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl_context))
    request = Request(url, headers={"User-Agent": LINK_CHECK_USER_AGENT})
    try:
        with opener.open(request, timeout=LINK_CHECK_TIMEOUT_SECONDS) as response:
            return response.status
    except HTTPError as error:
        # 4xx/5xx tetep artinya server-nya ngejawab
        return error.code

def build_unverified_ssl_context():
    """Konteks SSL tanpa cek sertifikat, cuma dipake buat ngetes server-nya hidup (ga ada data yg dikirim)."""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context

def check_url(url):
    """Cek URL. Server ngejawab di bawah 500 (termasuk 401/403 halaman login) dianggap aktif."""
    if not url.lower().startswith(("http://", "https://")):
        return LinkCheckResult(LINK_STATUS_UNKNOWN, "URL harus diawali http:// atau https://")
    note_suffix = ""
    try:
        try:
            status_code = open_url(url, ssl.create_default_context())
        except OSError as error:
            if not is_cert_error(error):
                raise
            status_code = open_url(url, build_unverified_ssl_context())
            note_suffix = " · Sertifikat SSL tidak valid"
    except (OSError, HTTPException) as error:
        return LinkCheckResult(LINK_STATUS_DOWN, describe_connection_error(error))
    except ValueError:
        return LinkCheckResult(LINK_STATUS_UNKNOWN, "Format URL tidak valid")
    status = LINK_STATUS_UP if status_code < 500 else LINK_STATUS_DOWN
    return LinkCheckResult(status, f"HTTP {status_code}{note_suffix}")

def check_port(address, port):
    """Cek Address + Port: port kebuka berarti aktif."""
    try:
        with socket.create_connection((address, port), timeout=LINK_CHECK_TIMEOUT_SECONDS):
            pass
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

def check_entry_status(entry):
    """Cek satu link (tombol Cek Status) terus simpen hasilnya."""
    result = check_target(build_check_target(entry))
    save_check_result(entry.id, result)
    db.session.commit()
    db.session.refresh(entry)
    return result

def check_all_entry_status(max_worker_count=LINK_CHECK_MAX_WORKER_COUNT):
    """Cek semua link sekaligus (buat command terjadwal). Ngeceknya paralel, nyimpennya satu-satu. Return Counter per status."""
    entry_list = db.session.execute(db.select(AccessEntry).order_by(AccessEntry.id)).scalars().all()
    target_list = [build_check_target(entry) for entry in entry_list]
    with ThreadPoolExecutor(max_workers=max_worker_count) as executor:
        result_list = list(executor.map(check_target, target_list))
    for target, result in zip(target_list, result_list):
        save_check_result(target.entry_id, result)
    db.session.commit()
    return Counter(result.status for result in result_list)