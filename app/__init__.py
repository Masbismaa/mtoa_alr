"""App factory MTOA ALR: tempat aplikasi Flask dirakit (config, extension, model, blueprint, CLI)."""

import os

from flask import Flask, render_template

from app.config import CONFIG_BY_NAME_DICT
from app.extensions import csrf, db, limiter, login_manager, migrate
from app.utils.constants import OTP_DELIVERY_CONSOLE

# config yg wajib diisi, kalau kosong app langsung nolak jalan
REQUIRED_CONFIG_KEY_LIST = ["SECRET_KEY", "SQLALCHEMY_DATABASE_URI", "ENCRYPTION_KEY"]

def create_app(config_name=None):
    # 1. Pilih dan muat konfigurasi sesuai environment
    config_name = config_name or os.environ.get("APP_ENV", "development")
    app = Flask(__name__)
    app.config.from_object(CONFIG_BY_NAME_DICT[config_name])

    # 2. Fail-fast: cek semua config wajib & aturan keamanan
    validate_required_config(app)

    # 3. Hubungkan extension (dibuat sekali di extensions.py) ke aplikasi
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)

    # 4. Muat model + daftarin cara Flask-Login ngambil user dari session
    from app import models
    from app.security import login_loader

    # 5. Daftarkan route, halaman error, dan perintah CLI
    register_blueprints(app)
    register_error_handlers(app)

    from app.cli import register_cli_commands

    register_cli_commands(app)
    return app

def validate_required_config(app):
    """Cek config wajib udah keisi semua, kalau ada yg kosong/berbahaya langsung error."""
    # kumpulin dulu semua yg kosong biar pesan errornya lengkap sekali jalan
    missing_key_list = [key for key in REQUIRED_CONFIG_KEY_LIST if not app.config.get(key)]
    if missing_key_list:
        raise RuntimeError(f"Config belum di-set di file .env: {', '.join(missing_key_list)}")

    # pastiin ENCRYPTION_KEY formatnya bener, jangan nunggu error pas user nyimpen data
    from app.security.encryption_service import build_fernet

    build_fernet(app.config["ENCRYPTION_KEY"])

    # OTP yg muncul di terminal cuma boleh buat development
    if app.config.get("IS_PRODUCTION") and app.config.get("OTP_DELIVERY_MODE") == OTP_DELIVERY_CONSOLE:
        raise RuntimeError("OTP_DELIVERY_MODE=console dilarang di production, pakai smtp")

def register_blueprints(app):
    """Mendaftarkan seluruh blueprint (kumpulan route) ke aplikasi.

    Import dilakukan di dalam fungsi untuk menghindari erorr.
    """
    from app.routes.auth_routes import auth_bp
    from app.routes.health_routes import health_bp
    from app.routes.main_routes import main_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

def register_error_handlers(app):
    """Halaman error custmo."""

    @app.errorhandler(429)
    def handle_too_many_requests(error):
        """Muncul kalau user kena rate limit."""
        return render_template("pages/errors/429.html"), 429