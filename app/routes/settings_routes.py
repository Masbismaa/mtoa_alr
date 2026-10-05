"""Halaman Settings + API simpan preferensi tampilan."""
from flask import Blueprint, render_template, request
from flask_login import login_required

from app.extensions import limiter
from app.services.preference_service import build_ui_preference_dict, update_preference
from app.utils.exceptions import ValidationError
from app.utils.response_formatter import error_response, success_response
from app.utils.request_helper import get_current_user

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")

@settings_bp.get("/")
@login_required
def index():
    """Halaman profil + tombol buka UI Customizer."""
    return render_template("pages/settings.html", page_title="Settings")

@settings_bp.post("/preferences")
@login_required
@limiter.limit("30 per minute")
def update_preferences():
    """Simpan preferensi tampilan (dipanggil dari JS, body JSON, token CSRF di header)."""
    preference_payload = request.get_json(silent=True)
    if not isinstance(preference_payload, dict):
        return error_response("Data harus berupa JSON object", 400)

    try:
        preference = update_preference(get_current_user(), preference_payload)
    except ValidationError as error:
        return error_response("Preferensi tidak valid", 400, error.error_list)

    return success_response(data=build_ui_preference_dict(preference), message="Preferensi tersimpan")
