"""Halaman Settings (profil, ganti password) + API simpan preferensi tampilan."""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import login_required, login_user

from app.extensions import limiter
from app.security.role_guard import api_login_required
from app.schemas.auth_schema import ChangePasswordForm, ProfileForm
from app.services.auth_service import change_password, update_profile
from app.services.preference_service import (
    build_ui_preference_dict,
    delete_selection_variant,
    save_selection_variant,
    update_preference,
    update_table_layout,
)
from app.utils.exceptions import AuthError, ValidationError
from app.utils.response_formatter import error_response, success_response
from app.utils.form_helper import flash_error_list
from app.utils.request_helper import get_current_user
from app.utils.url_helper import get_safe_back_url

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")

def render_settings(profile_form=None, password_form=None):
    """Halaman Settings. Form yg barusan dikirim (ada error-nya) dipake lagi, sisanya diisi data akun."""
    user = get_current_user()
    return render_template(
        "pages/settings.html",
        page_title="Settings",
        profile_form=profile_form or ProfileForm(obj=user, formdata=None),
        password_form=password_form or ChangePasswordForm(formdata=None),
    )

@settings_bp.get("/")
@login_required
def index():
    """Profil (bisa diedit), ganti password, & tombol buka UI Customizer."""
    return render_settings()

@settings_bp.post("/profile")
@login_required
@limiter.limit("10 per minute")
def update_profile_page():
    """Simpan nama, departemen, jabatan."""
    form = ProfileForm()
    if form.validate_on_submit():
        try:
            update_profile(get_current_user(), form.full_name.data, form.department.data, form.job_title.data)
        except AuthError as error:
            flash(str(error), "danger")
        else:
            flash("Profile saved", "success")
            return redirect(url_for("settings.index"))
    return render_settings(profile_form=form)

@settings_bp.post("/password")
@login_required
@limiter.limit("5 per minute")
def change_password_page():
    """Ganti password. Sesi lain ke-logout; sesi ini dibikin ulang biar tetep login."""
    form = ChangePasswordForm()
    if form.validate_on_submit():
        try:
            user = change_password(get_current_user(), form.current_password.data, form.password.data)
        except AuthError as error:
            flash(str(error), "danger")
        else:
            # session_version naik -> id login lama udah ga berlaku. Session baru yg bersih, terus login-in lagi
            session.clear()
            login_user(user)
            session.permanent = True
            flash("Password changed. Other sessions have been logged out.", "success")
            return redirect(url_for("settings.index"))
    return render_settings(password_form=form)

@settings_bp.post("/variants")
@login_required
@limiter.limit("30 per minute")
def save_variant():
    """Save as Variant: simpen isian Kriteria Pencarian layar itu pake nama, terus balik ke layar yg sama."""
    screen_path = request.form.get("screen_path", "")
    query_text = request.form.get("query_text", "")
    try:
        variant = save_selection_variant(get_current_user(), screen_path, request.form.get("name"), query_text)
    except ValidationError as error:
        flash_error_list(error.error_list)
        return redirect(get_safe_back_url(screen_path) or url_for("main.home"))
    flash(f'Variant "{variant.name}" saved', "success")
    return redirect(variant.screen_path + ("?" + variant.query_text if variant.query_text else ""))

@settings_bp.post("/variants/<int:variant_id>/delete")
@login_required
def delete_variant(variant_id):
    """Hapus variant punya sendiri."""
    screen_path = delete_selection_variant(get_current_user(), variant_id)
    if screen_path is None:
        flash("Variant not found", "warning")
        return redirect(url_for("main.home"))
    flash("Variant deleted", "success")
    return redirect(screen_path)

@settings_bp.post("/preferences")
@api_login_required
@limiter.limit("30 per minute")
def update_preferences():
    """Simpan preferensi tampilan (dipanggil dari JS, body JSON, token CSRF di header)."""
    preference_payload = request.get_json(silent=True)
    if not isinstance(preference_payload, dict):
        return error_response("Data must be a JSON object", 400)

    try:
        preference = update_preference(get_current_user(), preference_payload)
    except ValidationError as error:
        return error_response("Invalid preferences", 400, error.error_list)

    return success_response(data=build_ui_preference_dict(preference), message="Preferences saved")

@settings_bp.post("/table-layout")
@api_login_required
@limiter.limit("60 per minute")
def update_table_layout_api():
    """Simpen layout tabel ala ALV (kolom disembunyiin + lebar), dipanggil dari JS tabel. Token CSRF di header."""
    layout_payload = request.get_json(silent=True)
    if not isinstance(layout_payload, dict):
        return error_response("Data must be a JSON object", 400)

    try:
        layout_dict, is_stale = update_table_layout(get_current_user(), layout_payload)
    except ValidationError as error:
        return error_response("Invalid table layout", 400, error.error_list)

    # kiriman basi bukan error: udah ada perubahan yg lebih baru kesimpen
    message = "A newer layout change is already saved" if is_stale else "Table layout saved"
    return success_response(data={**layout_dict, "is_stale": is_stale}, message=message)
