"""Panel admin untuk pengaturan dan pemeriksaan Link Monitoring."""
from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.extensions import limiter
from app.schemas.link_monitor_schema import LinkMonitorSettingsForm
from app.security.role_guard import admin_required
from app.services.link_monitor_service import get_monitor_settings, run_monitor, update_monitor_settings
from app.utils.constants import LINK_STATUS_DOWN, LINK_STATUS_UNKNOWN, LINK_STATUS_UP

link_monitor_bp = Blueprint("link_monitor", __name__, url_prefix="/link-monitoring")


def render_monitor_page(form, settings):
    return render_template("pages/link_monitoring/index.html", page_title="Link Monitoring", form=form, settings=settings)


@link_monitor_bp.get("/")
@login_required
@admin_required
def index():
    settings = get_monitor_settings()
    return render_monitor_page(LinkMonitorSettingsForm(obj=settings), settings)


@link_monitor_bp.post("/settings")
@login_required
@admin_required
@limiter.limit("10 per minute")
def save_settings():
    settings = get_monitor_settings()
    form = LinkMonitorSettingsForm()
    if form.validate_on_submit():
        update_monitor_settings(current_user._get_current_object(), form)
        flash("Pengaturan Link Monitoring disimpan", "success")
        return redirect(url_for("link_monitor.index"))
    return render_monitor_page(form, settings)


@link_monitor_bp.post("/run")
@login_required
@admin_required
@limiter.limit("2 per hour")
def run_now():
    status_counter = run_monitor(force=True)
    total_count = sum(status_counter.values())
    flash(
        f"Pemeriksaan selesai: {total_count} data · {status_counter[LINK_STATUS_UP]} aktif · "
        f"{status_counter[LINK_STATUS_DOWN]} tidak aktif · {status_counter[LINK_STATUS_UNKNOWN]} belum dicek",
        "success",
    )
    return redirect(url_for("link_monitor.index"))
