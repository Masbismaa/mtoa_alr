"""Helper untuk membaca informasi request aktif."""

from flask import has_request_context, request
from flask_login import current_user

MAX_USER_AGENT_LENGTH = 255

def get_current_user():
    """Ambil objek pengguna dari proxy Flask-Login pada request aktif."""
    return current_user._get_current_object()

def get_client_ip():
    """IP klien pada request aktif, atau None di luar request.

    X-Forwarded-For tidak digunakan sebelum reverse proxy tepercaya dikonfigurasi.
    """
    if not has_request_context():
        return None
    return request.remote_addr

def get_user_agent():
    """User-Agent request aktif, dibatasi agar sesuai ukuran kolom database."""
    if not has_request_context():
        return None
    user_agent_text = request.user_agent.string or ""
    return user_agent_text[:MAX_USER_AGENT_LENGTH] or None

