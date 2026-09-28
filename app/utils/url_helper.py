"""Validasi & rapihin URL, address, dan port (SR-06)."""

import re
from urllib.parse import urlsplit, urlunsplit

from app.utils.constants import ALLOWED_URL_SCHEME_SET, MAX_ADDRESS_LENGTH, MAX_URL_LENGTH

# address: hostname / IPv4 / IPv6 (huruf, angka, titik, strip, titik dua, kurung siku)
ADDRESS_PATTERN = re.compile(r"^[a-z0-9.\-:\[\]]+$")

def normalize_url(raw_url):
    """Validasi URL terus dirapihin biar gampang dicek duplikatnya.

    - wajib http/https
    - skema & host jadi huruf kecil, garis miring di akhir dibuang
    - ga boleh ada spasi atau username/password di dalem URL

    Lempar ValueError (pesannya aman ditampilin) kalau ga sesuai.
    """
    url_text = (raw_url or "").strip()
    if not url_text:
        raise ValueError("URL wajib diisi")
    if len(url_text) > MAX_URL_LENGTH:
        raise ValueError(f"URL maksimal {MAX_URL_LENGTH} karakter")
    if any(character.isspace() for character in url_text):
        raise ValueError("URL tidak boleh mengandung spasi")

    try:
        url_part = urlsplit(url_text)
        hostname = url_part.hostname
        # dipanggil biar port yg ngaco (misal :99999) ketahuan
        url_part.port
    except ValueError as error:
        raise ValueError("Format URL tidak valid") from error

    if url_part.scheme.lower() not in ALLOWED_URL_SCHEME_SET:
        raise ValueError("URL wajib diawali http:// atau https://")
    if not hostname:
        raise ValueError("Format URL tidak valid")
    if url_part.username or url_part.password:
        raise ValueError("Jangan taruh username/password di URL, pakai kolom Username & Access Note")

    return urlunsplit((
        url_part.scheme.lower(),
        url_part.netloc.lower(),
        url_part.path.rstrip("/"),
        url_part.query,
        url_part.fragment,
    ))

def normalize_address(raw_address):
    """Validasi address (IP / hostname), dirapihin jadi huruf kecil."""
    address_text = (raw_address or "").strip().lower()
    if not address_text:
        raise ValueError("Address wajib diisi")
    if len(address_text) > MAX_ADDRESS_LENGTH:
        raise ValueError(f"Address maksimal {MAX_ADDRESS_LENGTH} karakter")
    if not ADDRESS_PATTERN.match(address_text):
        raise ValueError("Address cuma boleh huruf, angka, titik, strip, atau titik dua (contoh: 10.0.0.1)")
    return address_text

def parse_port(raw_port):
    """Ubah input port jadi angka 1-65535. Kosong -> None."""
    if raw_port is None or str(raw_port).strip() == "":
        return None
    try:
        port_number = int(str(raw_port).strip())
    except ValueError as error:
        raise ValueError("Port harus berupa angka") from error
    if not 1 <= port_number <= 65535:
        raise ValueError("Port harus di antara 1 dan 65535")
    return port_number