"""Pembatas percobaan login per email & kode lupa password (pakai `limits` langsung)."""
# bukan Flask-Limiter: itu mati total kalau RATELIMIT_ENABLED=False, padahal ini aturan keamanan login
import math
import time

from flask import current_app
from limits import parse
from limits.storage import storage_from_string
from limits.strategies import MovingWindowRateLimiter

from app.utils.constants import (
    LOGIN_LOCK_MINUTES,
    LOGIN_MAX_FAILED_COUNT,
    RESET_ATTEMPT_MAX_COUNT,
    RESET_CODE_DAILY_MAX_COUNT,
    RESET_CODE_MAX_COUNT,
    RESET_CODE_WINDOW_MINUTES,
)

EXTENSION_KEY = "auth_throttle"
LOGIN_FAILURE_LIMIT = parse(f"{LOGIN_MAX_FAILED_COUNT} per {LOGIN_LOCK_MINUTES} minutes")
RESET_CODE_LIMIT = parse(f"{RESET_CODE_MAX_COUNT} per {RESET_CODE_WINDOW_MINUTES} minutes")
LOGIN_FAILURE_NAMESPACE = "login_failure"
RESET_CODE_NAMESPACE = "reset_code"
RESET_CODE_DAILY_LIMIT = parse(f"{RESET_CODE_DAILY_MAX_COUNT} per 1 day")
RESET_CODE_DAILY_NAMESPACE = "reset_code_daily"
RESET_ATTEMPT_LIMIT = parse(f"{RESET_ATTEMPT_MAX_COUNT} per 1 day")
RESET_ATTEMPT_NAMESPACE = "reset_attempt"

def init_auth_throttle(app):
    """Dipanggil sekali dari create_app: siapin penyimpanan hitungan buat app ini."""
    storage = storage_from_string(app.config["RATELIMIT_STORAGE_URI"])
    app.extensions[EXTENSION_KEY] = MovingWindowRateLimiter(storage)

def get_limiter():
    return current_app.extensions[EXTENSION_KEY]

def get_login_block_minutes(email):
    """0 kalau email ini boleh nyoba login; kalau keblokir = sisa menit sampai boleh nyoba lagi."""
    limiter = get_limiter()
    if limiter.test(LOGIN_FAILURE_LIMIT, LOGIN_FAILURE_NAMESPACE, email):
        return 0
    reset_time = limiter.get_window_stats(LOGIN_FAILURE_LIMIT, LOGIN_FAILURE_NAMESPACE, email).reset_time
    return max(1, math.ceil((reset_time - time.time()) / 60))

def record_login_failure(email):
    """Catat 1 kali gagal. Return True kalau gagal yg ini bikin email itu BARU AJA keblokir (buat notifikasi sekali)."""
    limiter = get_limiter()
    limiter.hit(LOGIN_FAILURE_LIMIT, LOGIN_FAILURE_NAMESPACE, email)
    return not limiter.test(LOGIN_FAILURE_LIMIT, LOGIN_FAILURE_NAMESPACE, email)

def clear_login_failure(email):
    """Login berhasil / akun di-unlock admin / reset password: hitungan gagal email ini dinolin lagi."""
    get_limiter().clear(LOGIN_FAILURE_LIMIT, LOGIN_FAILURE_NAMESPACE, email)

def allow_reset_code(email):
    """True kalau kode lupa password boleh dikirim ke email ini sekarang."""
    return (get_limiter().hit(RESET_CODE_LIMIT, RESET_CODE_NAMESPACE, email)
            and get_limiter().hit(RESET_CODE_DAILY_LIMIT, RESET_CODE_DAILY_NAMESPACE, email))

def allow_reset_attempt(email, ip_address):
    """True kalau email + IP ini masih boleh nyoba kode lupa password hari ini."""
    return get_limiter().hit(RESET_ATTEMPT_LIMIT, RESET_ATTEMPT_NAMESPACE, email, ip_address)
