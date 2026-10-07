"""Konfigurasi aplikasi ALR untuk setiap environment (development, production, testing)."""
import os
from datetime import timedelta
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Baca isi file .env ke environment variable sebelum class config dibuat
load_dotenv()

# folder root project (sejajar run.py)
BASE_DIR = Path(__file__).resolve().parent.parent

class BaseConfig:
    """Konfigurasi dasar yang diwarisi oleh semua environment."""

    # Kunci rahasia & koneksi database (diambil dari .env, tidak ditulis di kode)
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Kunci untuk enkripsi access note.
    ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY")

    # Penanda environment produksi untuk validasi saat aplikasi dimulai.
    IS_PRODUCTION = False

    # Batas ukuran request: 5 file x 10MB + ruang untuk field form lainnya
    MAX_CONTENT_LENGTH = 55 * 1024 * 1024

    # Lampiran berada di luar static agar tidak dapat diakses langsung.
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER") or str(BASE_DIR / "uploads")

    # Keamanan cookie session: tidak bisa dibaca JavaScript (anti XSS pencurian session)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Sesi berakhir setelah delapan jam.
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # Proteksi CSRF aktif untuk semua form
    WTF_CSRF_ENABLED = True

    # Login & OTP
    # Domain email yang diizinkan untuk pendaftaran.
    ALLOWED_EMAIL_DOMAIN = os.environ.get("ALLOWED_EMAIL_DOMAIN", "spindo.com")
    # console untuk development; smtp disediakan untuk implementasi production.
    OTP_DELIVERY_MODE = os.environ.get("OTP_DELIVERY_MODE", "console")

    # Rate limit (anti brute force)
    RATELIMIT_ENABLED = True
    # memory hanya sesuai untuk satu proses aplikasi.
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True

    # label environment di status bar bawah (DEV / TEST / PROD)
    APP_ENV_LABEL = "DEV"

class DevelopmentConfig(BaseConfig):
    """Konfigurasi saat development di laptop (debug aktif)."""

    DEBUG = True

class ProductionConfig(BaseConfig):
    """Konfigurasi server produksi (debug mati, cookie hanya lewat HTTPS)."""

    DEBUG = False
    IS_PRODUCTION = True
    SESSION_COOKIE_SECURE = True
    # server uji yg pake config produksi bisa ngisi APP_ENV_LABEL=TEST di .env
    APP_ENV_LABEL = os.environ.get("APP_ENV_LABEL", "PROD")

class TestingConfig(BaseConfig):
    """Konfigurasi khusus Pytest (database SQLite di memori, tanpa PostgreSQL)."""

    TESTING = True
    APP_ENV_LABEL = "TEST"
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    # Kunci enkripsi acak untuk setiap test run.
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    # CSRF dinonaktifkan hanya untuk test.
    WTF_CSRF_ENABLED = False
    # Rate limit dinonaktifkan secara default pada test.
    RATELIMIT_ENABLED = False
    ALLOWED_EMAIL_DOMAIN = "spindo.com"
    OTP_DELIVERY_MODE = "console"

# Pemetaan nama environment ke class config, dipakai oleh create_app()
CONFIG_BY_NAME_DICT = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
