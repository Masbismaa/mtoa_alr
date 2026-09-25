"""Konfigurasi aplikasi MTOA ALR untuk setiap environment (development, production, testing)."""
import os
from datetime import timedelta

from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Baca isi file .env ke environment variable sebelum class config dibuat
load_dotenv()

class BaseConfig:
    """Konfigurasi dasar yang diwarisi oleh semua environment."""
    # Kunci rahasia & koneksi database (diambil dari .env, tidak ditulis di kode)
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # kunci buat enkripsi password/access note, jangan sampe ilang
    ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY")

    # penanda server produksi, dipake buat cek keamanan pas app start
    IS_PRODUCTION = False

    # Batas ukuran request: 5 file x 10MB + ruang untuk field form lainnya (SR-07)
    MAX_CONTENT_LENGTH = 55 * 1024 * 1024

    # Keamanan cookie session: tidak bisa dibaca JavaScript (anti XSS pencurian session("Bismillah"))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # abis 8 jam user harus login ulang
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # Proteksi CSRF aktif untuk semua form
    WTF_CSRF_ENABLED = True

    # Login & OTP
    # cuma email domain ini yg boleh daftar
    ALLOWED_EMAIL_DOMAIN = os.environ.get("ALLOWED_EMAIL_DOMAIN", "spindo.com")
    # console = OTP muncul di terminal (buat development), smtp = lewat Intramail (soon cyak....)
    OTP_DELIVERY_MODE = os.environ.get("OTP_DELIVERY_MODE", "console")

    # Rate limit (anti brute force("Bismillah"))
    RATELIMIT_ENABLED = True
    # memory cukup buat 1 server, nanti di production ganti redis
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True

class DevelopmentConfig(BaseConfig):
    """Konfigurasi saat development di laptop (debug aktif)."""

    DEBUG = True

class ProductionConfig(BaseConfig):
    """Konfigurasi server produksi (debug mati, cookie hanya lewat HTTPS)."""

    DEBUG = False
    IS_PRODUCTION = True
    SESSION_COOKIE_SECURE = True

class TestingConfig(BaseConfig):
    """Konfigurasi khusus Pytest (database SQLite di memori, tanpa PostgreSQL)."""

    TESTING = True
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    # key enkripsi khusus test, dibikin random tiap kali test jalan
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    # CSRF dimatikan hanya saat test agar request test tidak perlu token
    WTF_CSRF_ENABLED = False
    # rate limit dimatiin biar test ga ke-blok, ada 1 test khusus yg nyalain
    RATELIMIT_ENABLED = False
    ALLOWED_EMAIL_DOMAIN = "spindo.com"
    OTP_DELIVERY_MODE = "console"

# Pemetaan nama environment ke class config, dipakai oleh create_app()
CONFIG_BY_NAME_DICT = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}