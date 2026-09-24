"""App factory MTOA ALR: tempat aplikasi Flask dirakit (config, extension, model, blueprint, CLI)."""

import os

from flask import Flask

from app.config import CONFIG_BY_NAME_DICT
from app.extensions import csrf, db, migrate


def create_app(config_name=None):
    """Membuat dan mengembalikan instance aplikasi Flask.

    Args:
        config_name: nama environment ("development", "production", "testing").
            Jika kosong, diambil dari variabel APP_ENV di .env.

    Returns:
        Objek aplikasi Flask yang siap dijalankan.
    """
    # --- 1. Pilih dan muat konfigurasi sesuai environment ---
    config_name = config_name or os.environ.get("APP_ENV", "development")
    app = Flask(__name__)
    app.config.from_object(CONFIG_BY_NAME_DICT[config_name])

    # --- 2. Fail-fast: tolak jalan jika konfigurasi rahasia belum di-set ---
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY belum di-set di file .env")
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError("DATABASE_URL belum di-set di file .env")

    # --- 3. Hubungkan extension (dibuat sekali di extensions.py) ke aplikasi ---
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # --- 4. Muat semua model agar terdaftar di metadata (dibutuhkan migrasi) ---
    from app import models  # noqa: F401

    # --- 5. Daftarkan route (blueprint) dan perintah CLI ---
    register_blueprints(app)

    from app.cli import register_cli_commands

    register_cli_commands(app)
    return app


def register_blueprints(app):
    """Mendaftarkan seluruh blueprint (kumpulan route) ke aplikasi.

    Import dilakukan di dalam fungsi untuk menghindari circular import.
    """
    from app.routes.health_routes import health_bp

    app.register_blueprint(health_bp)