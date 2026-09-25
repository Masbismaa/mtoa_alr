"""App factory MTOA ALR."""
import os

from flask import Flask, render_template, request
from flask_login import current_user

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

    # 5. Daftarkan route, halaman error, helper template, dan perintah CLI
    register_blueprints(app)
    register_error_handlers(app)
    register_template_helpers(app)

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

    Import dilakukan di dalam fungsi untuk menghindari circular import.
    """
    from app.routes.auth_routes import auth_bp
    from app.routes.health_routes import health_bp
    from app.routes.main_routes import main_bp
    from app.routes.settings_routes import settings_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(settings_bp)

def register_error_handlers(app):
    """Halaman error custom."""

    @app.errorhandler(429)
    def handle_too_many_requests(error):
        """Muncul kalau user kena rate limit."""
        return render_template("pages/errors/429.html"), 429

def register_template_helpers(app):
    """Filter & data global buat semua template (layout, sidebar, preferensi)."""
    from app.services.preference_service import build_ui_preference_dict, get_or_create_preference
    from app.utils.constants import ACCENT_COLOR_OPTION_LIST, FONT_FAMILY_OPTION_LIST
    from app.utils.navigation import build_sidebar_nav_list
    from app.utils.text_helper import get_initials, get_role_label

    # dipake di template: {{ nama | initials }}, {{ role | role_label }}
    app.add_template_filter(get_initials, "initials")
    app.add_template_filter(get_role_label, "role_label")

    @app.context_processor
    def inject_layout_context():
        """Data yg otomatis ada di semua template."""
        # halaman publik (login/register) ga butuh sidebar & preferensi dari DB
        if not current_user.is_authenticated:
            return {"ui_preference_dict": None, "sidebar_nav_list": []}

        user = current_user._get_current_object()
        preference = get_or_create_preference(user)
        return {
            "ui_preference_dict": build_ui_preference_dict(preference),
            "sidebar_nav_list": build_sidebar_nav_list(user, request.endpoint),
            "accent_color_option_list": ACCENT_COLOR_OPTION_LIST,
            "font_family_option_list": FONT_FAMILY_OPTION_LIST,
        }