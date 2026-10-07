"""Panel admin Link Monitoring: ringkasan status + tombol cek semua."""
from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import login_required
from app.extensions import limiter
from app.security.role_guard import admin_required
from app.services.link_monitor_service import build_monitor_summary, get_monitor_run, request_monitor_run
from app.utils.exceptions import ValidationError
from app.utils.form_helper import flash_error_list

link_monitor_bp = Blueprint("link_monitor", __name__, url_prefix="/link-monitoring")

@link_monitor_bp.get("/")
@login_required
@admin_required
def index():
    return render_template(
        "pages/link_monitoring/index.html",
        page_title="Link Monitoring",
        monitor_summary=build_monitor_summary(),
        monitor_run=get_monitor_run(),
    )

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
        flash("Pemeriksaan diantrekan. Hasil akan diperbarui saat pemeriksaan selesai.", "success")
    return redirect(url_for("link_monitor.index"))
