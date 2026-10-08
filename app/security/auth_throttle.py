"""Pembatas percobaan login (per email + IP) dan jeda email pemberitahuan register.

Kenapa per email + IP, bukan per akun: kalau per akun, siapa pun yg tau email orang bisa sengaja salah password
5x dan ngunci akun itu terus-terusan. Dengan email + IP, yg keblokir cuma IP si penyerang buat email itu;
pemilik akun dari PC-nya sendiri tetep bisa login.

Sengaja pakai library `limits` langsung (bukan dekorator Flask-Limiter): Flask-Limiter mati total kalau
RATELIMIT_ENABLED=False (misal di test), padahal pembatas ini bagian dari aturan keamanan login, bukan sekadar anti spam.
Penyimpanannya sama dgn rate limit (RATELIMIT_STORAGE_URI): memory di laptop/test, Redis di production
(wajib, biar semua proses server ngitung bareng).
"""
import math
import time

from flask import current_app, has_request_context, request
from limits import parse
from limits.storage import storage_from_string
from limits.strategies import MovingWindowRateLimiter

from app.utils.constants import (
    LOGIN_LOCK_MINUTES,
    LOGIN_MAX_FAILED_COUNT,
    REGISTER_CODE_MAX_COUNT,
    REGISTER_CODE_WINDOW_MINUTES,
    REGISTER_NOTICE_COOLDOWN_MINUTES,
)

EXTENSION_KEY = "auth_throttle"
LOGIN_FAILURE_LIMIT = parse(f"{LOGIN_MAX_FAILED_COUNT} per {LOGIN_LOCK_MINUTES} minutes")
REGISTER_NOTICE_LIMIT = parse(f"1 per {REGISTER_NOTICE_COOLDOWN_MINUTES} minutes")
REGISTER_CODE_LIMIT = parse(f"{REGISTER_CODE_MAX_COUNT} per {REGISTER_CODE_WINDOW_MINUTES} minutes")
LOGIN_FAILURE_NAMESPACE = "login_failure"
REGISTER_NOTICE_NAMESPACE = "register_notice"
REGISTER_CODE_NAMESPACE = "register_code"

def init_auth_throttle(app):
    """Dipanggil sekali dari create_app: siapin penyimpanan hitungan buat app ini."""
    storage = storage_from_string(app.config["RATELIMIT_STORAGE_URI"])
    app.extensions[EXTENSION_KEY] = MovingWindowRateLimiter(storage)

def get_limiter():
    return current_app.extensions[EXTENSION_KEY]

def get_client_ip():
    """IP pengirim request (udah bener di balik reverse proxy lewat ProxyFix). Di luar request (CLI/test service) = '-'."""
    if has_request_context():
        return request.remote_addr or "-"
    return "-"

def get_login_block_minutes(email, ip_address):
    """0 kalau email+IP ini boleh nyoba login; kalau keblokir = sisa menit sampai boleh nyoba lagi."""
    limiter = get_limiter()
    if limiter.test(LOGIN_FAILURE_LIMIT, LOGIN_FAILURE_NAMESPACE, email, ip_address):
        return 0
    reset_time = limiter.get_window_stats(LOGIN_FAILURE_LIMIT, LOGIN_FAILURE_NAMESPACE, email, ip_address).reset_time
    return max(1, math.ceil((reset_time - time.time()) / 60))

def record_login_failure(email, ip_address):
    """Catat 1 kali gagal. Return True kalau gagal yg ini bikin email+IP itu BARU AJA keblokir (buat notifikasi sekali)."""
    limiter = get_limiter()
    limiter.hit(LOGIN_FAILURE_LIMIT, LOGIN_FAILURE_NAMESPACE, email, ip_address)
    return not limiter.test(LOGIN_FAILURE_LIMIT, LOGIN_FAILURE_NAMESPACE, email, ip_address)

def clear_login_failure(email, ip_address):
    """Login berhasil: hitungan gagal email+IP ini dinolin lagi."""
    get_limiter().clear(LOGIN_FAILURE_LIMIT, LOGIN_FAILURE_NAMESPACE, email, ip_address)

def allow_register_notice(email):
    """True kalau email pemberitahuan register boleh dikirim ke alamat ini sekarang (anti spam ke pemilik email)."""
    return get_limiter().hit(REGISTER_NOTICE_LIMIT, REGISTER_NOTICE_NAMESPACE, email)

def allow_register_code(email):
    """True kalau kode verifikasi daftar boleh dikirim ke alamat ini sekarang. Batasnya per email (bukan per IP),
    biar orang ga bisa ngebanjirin kotak masuk orang lain pake banyak percobaan daftar."""
    return get_limiter().hit(REGISTER_CODE_LIMIT, REGISTER_CODE_NAMESPACE, email)
