"""Pembatas percobaan login (per email) dan jeda email pemberitahuan register.

Salah password juga ngunci akunnya (users.locked_until, lihat auth_service). Pembatas per email ini tetep ada
biar email ga terdaftar keblokir dgn pesan yg sama persis (ga ngebocorin email mana yg terdaftar), dan
sengaja ga pakai IP supaya admin bisa ngebuka blokirnya bareng kunci akun (clear_login_failure).
Konsekuensinya: orang yg tau email kita bisa ngunci akun kita 15 menit dgn sengaja salah password.

Sengaja pakai library `limits` langsung (bukan dekorator Flask-Limiter): Flask-Limiter mati total kalau
RATELIMIT_ENABLED=False (misal di test), padahal pembatas ini bagian dari aturan keamanan login, bukan sekadar anti spam.
Penyimpanannya sama dgn rate limit (RATELIMIT_STORAGE_URI): memory di laptop/test, Redis di production
(wajib, biar semua proses server ngitung bareng).
"""
import math
import time

from flask import current_app
from limits import parse
from limits.storage import storage_from_string
from limits.strategies import MovingWindowRateLimiter

from app.utils.constants import (
    LOGIN_LOCK_MINUTES,
    LOGIN_MAX_FAILED_COUNT,
    REGISTER_CODE_MAX_COUNT,
    REGISTER_CODE_WINDOW_MINUTES,
    REGISTER_NOTICE_COOLDOWN_MINUTES,
    RESET_ATTEMPT_MAX_COUNT,
    RESET_CODE_DAILY_MAX_COUNT,
)

EXTENSION_KEY = "auth_throttle"
LOGIN_FAILURE_LIMIT = parse(f"{LOGIN_MAX_FAILED_COUNT} per {LOGIN_LOCK_MINUTES} minutes")
REGISTER_NOTICE_LIMIT = parse(f"1 per {REGISTER_NOTICE_COOLDOWN_MINUTES} minutes")
REGISTER_CODE_LIMIT = parse(f"{REGISTER_CODE_MAX_COUNT} per {REGISTER_CODE_WINDOW_MINUTES} minutes")
LOGIN_FAILURE_NAMESPACE = "login_failure"
REGISTER_NOTICE_NAMESPACE = "register_notice"
REGISTER_CODE_NAMESPACE = "register_code"
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

def allow_register_notice(email):
    """True kalau email pemberitahuan register boleh dikirim ke alamat ini sekarang (anti spam ke pemilik email)."""
    return get_limiter().hit(REGISTER_NOTICE_LIMIT, REGISTER_NOTICE_NAMESPACE, email)

def allow_register_code(email):
    """True kalau kode verifikasi daftar boleh dikirim ke alamat ini sekarang. Batasnya per email (bukan per IP),
    biar orang ga bisa ngebanjirin kotak masuk orang lain pake banyak percobaan daftar."""
    return get_limiter().hit(REGISTER_CODE_LIMIT, REGISTER_CODE_NAMESPACE, email)

def allow_reset_code(email):
    """True kalau kode lupa password boleh dikirim ke alamat ini sekarang. Batasnya per email: sama kayak kode daftar
    (anti banjir kotak masuk) + batas harian. Batas harian ini yg ngebatesin total tebakan kode lintas IP
    (tiap kode cuma bisa dicoba OTP_MAX_ATTEMPT_COUNT kali)."""
    return (get_limiter().hit(REGISTER_CODE_LIMIT, RESET_CODE_NAMESPACE, email)
            and get_limiter().hit(RESET_CODE_DAILY_LIMIT, RESET_CODE_DAILY_NAMESPACE, email))

def allow_reset_attempt(email, ip_address):
    """True kalau email ini masih boleh nyoba kode lupa password hari ini dari IP ini. Per email + IP, biar orang lain
    yg sengaja salah-salahin kode ga bikin pemiliknya ga bisa reset (total tebakan udah kebatas di allow_reset_code)."""
    return get_limiter().hit(RESET_ATTEMPT_LIMIT, RESET_ATTEMPT_NAMESPACE, email, ip_address)
