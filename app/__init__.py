"""App factory ALR: tempat aplikasi Flask dirakit (config, extension, model, blueprint, CLI)."""
import os

from flask import Flask, render_template, request
from flask_login import current_user

from app.config import CONFIG_BY_NAME_DICT
from app.extensions import csrf, db, limiter, login_manager, migrate
from app.utils.constants import OTP_DELIVERY_CONSOLE

# config yg wajib diisi, kalau kosong app langsung nolak jalan
REQUIRED_CONFIG_KEY_LIST = ["SECRET_KEY", "SQLALCHEMY_DATABASE_URI", "ENCRYPTION_KEY"]

# isi halaman error
ERROR_PAGE_DICT = {
    403: ("Akses ditolak", "Kamu tidak punya izin untuk membuka atau mengubah data ini."),
    404: ("Tidak ditemukan", "Halaman atau data yang kamu cari tidak ada, atau kamu tidak punya akses."),
    405: ("Aksi tidak diizinkan", "Cara membuka halaman ini tidak didukung. Kembali lalu coba lewat tombol yang tersedia."),
    413: ("File terlalu besar", "Total upload kebesaran. Maksimal 5 file, masing-masing 10MB."),
    500: ("Terjadi kesalahan", "Ada yang error di server. Coba lagi sebentar lagi, kalau masih muncul hubungi tim ICT."),
}
# token form (CSRF) kedaluwarsa / ga ada, biasanya gara-gara halaman kebuka kelamaan
CSRF_ERROR_PAGE = ("Sesi form kedaluwarsa", "Halaman ini kebuka terlalu lama. Muat ulang halaman, lalu kirim lagi.")


def resolve_config_name(config_name=None):
    """Nama environment yg dipake. Default production: lupa ngisi APP_ENV di server ga bikin pengaman production mati."""
    return config_name or os.environ.get("APP_ENV", "production")


def create_app(config_name=None):
    # 1. Pilih dan muat konfigurasi sesuai environment
    config_name = resolve_config_name(config_name)
    app = Flask(__name__)
    app.config.from_object(CONFIG_BY_NAME_DICT[config_name])
    # 2. Fail-fast: cek semua config wajib & aturan keamanan
    validate_required_config(app)
    proxy_count = app.config["TRUSTED_PROXY_COUNT"]
    if proxy_count:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxy_count, x_proto=proxy_count)

    # 3. Hubungkan extension (dibuat sekali di extensions.py) ke aplikasi
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)

    # 4. Muat model + daftarin cara Flask-Login ngambil user dari session
    from app import models  # noqa: F401
    from app.security import login_loader  # noqa: F401

    # 5. Daftarkan route, halaman error, helper template, dan perintah CLI
    register_blueprints(app)
    register_error_handlers(app)
    register_template_helpers(app)
    register_response_security(app)

    from app.cli import register_cli_commands

    register_cli_commands(app)
    return app

def validate_required_config(app):
    """Cek config wajib udah keisi semua, kalau ada yg kosong/berbahaya langsung error."""
    missing_key_list = [key for key in REQUIRED_CONFIG_KEY_LIST if not app.config.get(key)]
    if missing_key_list:
        raise RuntimeError(f"Config belum di-set di file .env: {', '.join(missing_key_list)}")

    from app.security.encryption_service import build_fernet

    build_fernet(app.config["ENCRYPTION_KEY"])

    if app.config.get("IS_PRODUCTION") and app.config.get("OTP_DELIVERY_MODE") == OTP_DELIVERY_CONSOLE:
        raise RuntimeError("OTP_DELIVERY_MODE=console dilarang di production, pakai smtp")
    if app.config["TRUSTED_PROXY_COUNT"] < 0 or app.config["UPLOAD_USER_QUOTA_BYTES"] <= 0:
        raise RuntimeError("Jumlah proxy dan kuota upload tidak valid")
    if app.config["OTP_DELIVERY_MODE"] == "smtp":
        if not app.config["SMTP_HOST"] or not app.config["SMTP_FROM"]:
            raise RuntimeError("SMTP_HOST dan SMTP_FROM wajib diisi untuk pengiriman OTP")
        if app.config["SMTP_SECURITY"] not in ("ssl", "starttls"):
            raise RuntimeError("SMTP_SECURITY harus ssl atau starttls")
    elif app.config["OTP_DELIVERY_MODE"] != OTP_DELIVERY_CONSOLE:
        raise RuntimeError("Mode pengiriman OTP tidak dikenal")
    if app.config.get("IS_PRODUCTION"):
        if app.config["RATELIMIT_STORAGE_URI"].startswith("memory://"):
            raise RuntimeError("Production membutuhkan penyimpanan rate limit bersama, misalnya Redis")
        if not app.config["UPLOAD_SCANNER_HOST"]:
            raise RuntimeError("Production membutuhkan UPLOAD_SCANNER_HOST (ClamAV)")


def register_response_security(app):
    @app.after_request
    def secure_response(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        # script cuma dari file sendiri: template ga punya <script> inline / onclick, jadi XSS yg lolos ga bisa jalanin script
        response.headers.setdefault(
            "Content-Security-Policy", "script-src 'self'; frame-ancestors 'none'; base-uri 'self'; object-src 'none'",
        )
        response.headers.setdefault("Referrer-Policy", "same-origin")
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "private, no-store"
        if app.config.get("IS_PRODUCTION"):
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return response

def register_blueprints(app):
    """Daftarin semua blueprint (import di dalem biar ga circular import)."""
    from app.routes.access_entry_routes import entries_bp
    from app.routes.attachment_routes import attachments_bp
    from app.routes.auth_routes import auth_bp
    from app.routes.health_routes import health_bp
    from app.routes.link_monitor_routes import link_monitor_bp
    from app.routes.main_routes import main_bp
    from app.routes.settings_routes import settings_bp
    from app.routes.group_routes import groups_bp
    from app.routes.audit_routes import audit_bp
    from app.routes.category_routes import categories_bp
    from app.routes.user_routes import users_bp
    from app.routes.notification_routes import notifications_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(link_monitor_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(entries_bp)
    app.register_blueprint(attachments_bp)
    app.register_blueprint(groups_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(notifications_bp)

def build_error_handler(error_code, error_title, error_message):
    """Bikin handler buat satu kode error (biar ga nulis ulang)."""

    def handle_error(error):
        if error_code >= 500:
            # Handler ini dipanggil saat ada request, jadi application context
            # dan session SQLAlchemy sudah tersedia di sini.
            db.session.rollback()
        return render_template(
            "pages/errors/error.html",
            error_code=error_code,
            error_title=error_title,
            error_message=error_message,
        ), error_code

    return handle_error

def register_error_handlers(app):
    """Halaman error custom."""
    from flask_wtf.csrf import CSRFError
    from app.utils.exceptions import PermissionDeniedError

    for error_code, (error_title, error_message) in ERROR_PAGE_DICT.items():
        app.register_error_handler(error_code, build_error_handler(error_code, error_title, error_message))

    forbidden_title, forbidden_message = ERROR_PAGE_DICT[403]
    app.register_error_handler(PermissionDeniedError, build_error_handler(403, forbidden_title, forbidden_message))
    app.register_error_handler(CSRFError, build_error_handler(400, *CSRF_ERROR_PAGE))

    @app.errorhandler(429)
    def handle_too_many_requests(error):
        return render_template("pages/errors/429.html"), 429

def register_template_helpers(app):
    """Filter & data global buat semua template."""
    from app.services.preference_service import build_ui_preference_dict, get_or_create_preference
    from app.services.user_notification_service import count_unread_notification, list_recent_notification
    from app.utils.constants import ACCENT_COLOR_OPTION_LIST, FONT_FAMILY_OPTION_LIST
    from app.services.category_service import build_category_label
    from app.utils.datetime_helper import format_local_datetime, format_time_ago
    from app.utils.navigation import build_sidebar_section_list
    from app.utils.sanitizer import render_rich_text
    from app.utils.text_helper import (
        format_file_size,
        get_initials,
        get_link_status_label,
        get_role_label,
        get_visibility_label,
        get_audit_action_label,
        get_audit_entity_label,
        get_user_status_label
    )

    app.add_template_filter(get_initials, "initials")
    app.add_template_filter(get_role_label, "role_label")
    app.add_template_filter(get_visibility_label, "visibility_label")
    app.add_template_filter(get_link_status_label, "link_status_label")
    app.add_template_filter(format_local_datetime, "local_datetime")
    app.add_template_filter(render_rich_text, "rich_text")
    app.add_template_filter(format_file_size, "file_size")
    app.add_template_filter(get_audit_action_label, "audit_action_label")
    app.add_template_filter(get_audit_entity_label, "audit_entity_label")
    app.add_template_filter(build_category_label, "category_label")
    app.add_template_filter(format_time_ago, "time_ago")
    app.add_template_filter(get_user_status_label, "user_status_label")

    from app.security.access_policy import has_permission, is_admin
    from app.utils.request_helper import get_current_user
    from app.utils.constants import PERMISSION_MANAGE_CATEGORIES, ROLE_ADMIN
    from app.utils.vite_manifest import vite_tags
    # dipake template buat nampilin/nyembunyiin tombol sesuai akses
    app.jinja_env.globals.update(
        has_permission=has_permission,
        is_admin=is_admin,
        # tag script komponen React hasil build (frontend/), misal {{ vite_tags("entry_table") }}
        vite_tags=vite_tags,
        PERMISSION_MANAGE_CATEGORIES=PERMISSION_MANAGE_CATEGORIES,
        ROLE_ADMIN=ROLE_ADMIN,
    )

    from app.services.category_service import clear_request_category_cache

    # cache kategori per request dimulai bersih (app context bisa dipake ulang antar request, misal di test)
    app.before_request(clear_request_category_cache)

    @app.context_processor
    def inject_layout_context():
        """Data yg otomatis ada di semua template."""
        if not current_user.is_authenticated:
            return {"ui_preference_dict": None, "sidebar_section_list": []}

        user = get_current_user()
        preference = get_or_create_preference(user)
        return {
            "ui_preference_dict": build_ui_preference_dict(preference),
            "sidebar_section_list": build_sidebar_section_list(user, request.endpoint),
            "accent_color_option_list": ACCENT_COLOR_OPTION_LIST,
            "font_family_option_list": FONT_FAMILY_OPTION_LIST,
            "unread_notification_count": count_unread_notification(user),
            "notification_list": list_recent_notification(user),
        }
