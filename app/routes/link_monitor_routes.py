"""Panel admin Link Monitoring: ringkasan status + tombol cek semua."""
from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import login_required
from app.extensions import limiter
from app.security.role_guard import admin_required
from app.services.link_monitor_service import build_monitor_summary, build_run_summary_text, run_monitor

link_monitor_bp = Blueprint("link_monitor", __name__, url_prefix="/link-monitoring")

@link_monitor_bp.get("/")
@login_required
@admin_required
def index():
    return render_template(
        "pages/link_monitoring/index.html",
        page_title="Link Monitoring",
        monitor_summary=build_monitor_summary(),
    )

@link_monitor_bp.post("/run")
@login_required
@admin_required
@limiter.limit("2 per hour")
def run_now():
    flash(build_run_summary_text(run_monitor()), "success")
    return redirect(url_for("link_monitor.index"))
