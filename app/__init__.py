"""App factory MTOA ALR: tempat aplikasi Flask dirakit (config, extension, model, blueprint, CLI)."""

import os

from flask import Flask

from app.config import CONFIG_BY_NAME_DICT
from app.extensions import csrf, db, migrate

# config yg wajib diisi, kalau kosong app langsung nolak jalan
REQUIRED_CONFIG_KEY_LIST = ["SECRET_KEY", "SQLALCHEMY_DATABASE_URI", "ENCRYPTION_KEY"]

def create_app(config_name=None):
    """Membuat dan mengembalikan instance aplikasi Flask.

    Args:
        config_name: nama environment ("development", "production", "testing").
            Jika kosong, diambil dari variabel APP_ENV di .env.

    Returns:
        Objek aplikasi Flask yang siap dijalankan.
    """
    # 1. Pilih dan muat konfigurasi sesuai environment
    config_name = config_name or os.environ.get("APP_ENV", "development")
    app = Flask(__name__)
    app.config.from_object(CONFIG_BY_NAME_DICT[config_name])

    # 2. Fail-fast: cek semua config wajib, sekalian validasi format ENCRYPTION_KEY
    validate_required_config(app)

    # 3. Hubungkan extension (dibuat sekali di extensions.py) ke aplikasi
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # 4. Muat semua model agar terdaftar di metadata (dibutuhkan migrasi)
    from app import models  # noqa: F401

    # 5. Daftarkan route (blueprint) dan perintah CLI
    register_blueprints(app)

    from app.cli import register_cli_commands

    register_cli_commands(app)
    return app

def validate_required_config(app):
    """Cek config wajib udah keisi semua, kalau ada yg kosong langsung error."""
    # kumpulin dulu semua yg kosong biar pesan errornya lengkap sekali jalan
    missing_key_list = [key for key in REQUIRED_CONFIG_KEY_LIST if not app.config.get(key)]
    if missing_key_list:
        raise RuntimeError(f"Config belum di-set di file .env: {', '.join(missing_key_list)}")

    # pastiin ENCRYPTION_KEY formatnya bener, jangan nunggu error pas user nyimpen data
    from app.security.encryption_service import build_fernet

    build_fernet(app.config["ENCRYPTION_KEY"])

def register_blueprints(app):
    """Mendaftarkan seluruh blueprint (kumpulan route) ke aplikasi.

    Import dilakukan di dalam fungsi untuk menghindari circular import.
    """
    from app.routes.health_routes import health_bp

    app.register_blueprint(health_bp)