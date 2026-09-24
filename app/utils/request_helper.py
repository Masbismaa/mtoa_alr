"""Ambil info dari request yg lagi jalan (IP, user agent)."""

from flask import has_request_context, request

MAX_USER_AGENT_LENGTH = 255

def get_client_ip():
    """IP user yg lagi akses. None kalau dipanggil di luar request (misal dari CLI).

    Sengaja ga baca X-Forwarded-For karena gampang dipalsuin.
    Kalau nanti pake reverse proxy, diatur lewat ProxyFix di milestone hardening.
    """
    if not has_request_context():
        return None
    return request.remote_addr

def get_user_agent():
    """Browser/aplikasi yg dipake user, dipotong biar muat di kolom DB."""
    if not has_request_context():
        return None
    user_agent_text = request.user_agent.string or ""
    return user_agent_text[:MAX_USER_AGENT_LENGTH] or None