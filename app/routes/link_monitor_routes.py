"""Panel admin Link Monitoring: ringkasan status + tombol cek semua + status pemeriksaan (polling)."""
from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from app.extensions import limiter
from app.security.access_policy import is_admin
from app.security.role_guard import admin_required, api_login_required
from app.services.link_monitor_service import build_monitor_status, build_monitor_summary, request_monitor_run
from app.utils.exceptions import ValidationError
from app.utils.form_helper import flash_error_list
from app.utils.response_formatter import error_response, success_response

link_monitor_bp = Blueprint("link_monitor", __name__, url_prefix="/link-monitoring")

@link_monitor_bp.get("/")
@login_required
@admin_required
def index():
    return render_template(
        "pages/link_monitoring/index.html",
        page_title="Link Monitoring",
        monitor_summary=build_monitor_summary(),
        monitor_status=build_monitor_status(),
    )

@link_monitor_bp.get("/status")
@api_login_required
@limiter.limit("60 per minute")
def status():
    """Status pemeriksaan (JSON) buat halaman yg lagi kebuka: progres jalan sendiri tanpa reload."""
    if not is_admin(current_user):
        return error_response("This page is for admins only", 403)
    return success_response(data=build_monitor_status())

@link_monitor_bp.post("/run")
@login_required
@admin_required
@limiter.limit("2 per hour")
def run_now():
    try:
        request_monitor_run()
    except ValidationError as error:
        flash_error_list(error.error_list)
    else:
        flash("The check has been queued. Results will update when the check finishes.", "success")
    return redirect(url_for("link_monitor.index"))
