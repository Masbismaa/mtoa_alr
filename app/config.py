"""Konfigurasi aplikasi MTOA ALR untuk setiap environment (development, production, testing)."""

import os

from dotenv import load_dotenv

# Baca isi file .env ke environment variable sebelum class config dibuat
load_dotenv()


class BaseConfig:
    """Konfigurasi dasar yang diwarisi oleh semua environment."""

    # --- Kunci rahasia & koneksi database (diambil dari .env, tidak ditulis di kode) ---
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Batas ukuran request: 5 file x 10MB + ruang untuk field form lainnya (SR-07) ---
    MAX_CONTENT_LENGTH = 55 * 1024 * 1024

    # --- Keamanan cookie session: tidak bisa dibaca JavaScript (anti XSS pencurian session) ---
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # --- Proteksi CSRF aktif untuk semua form ---
    WTF_CSRF_ENABLED = True


class DevelopmentConfig(BaseConfig):
    """Konfigurasi saat development di laptop (debug aktif)."""

    DEBUG = True


class ProductionConfig(BaseConfig):
    """Konfigurasi server produksi (debug mati, cookie hanya lewat HTTPS)."""

    DEBUG = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(BaseConfig):
    """Konfigurasi khusus Pytest (database SQLite di memori, tanpa PostgreSQL)."""

    TESTING = True
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    # CSRF dimatikan hanya saat test agar request test tidak perlu token
    WTF_CSRF_ENABLED = False


# Pemetaan nama environment ke class config, dipakai oleh create_app()
CONFIG_BY_NAME_DICT = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}