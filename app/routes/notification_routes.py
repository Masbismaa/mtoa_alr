"""Route notifikasi lonceng: buka satu notifikasi, tandain semua dibaca."""
from flask import Blueprint, abort, redirect, request, url_for
from flask_login import login_required
from app.services.user_notification_service import mark_all_notification_read, open_notification
from app.utils.request_helper import get_current_user
from app.utils.url_helper import get_safe_back_url

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")

def read_back_url():
    """Balik ke layar asal (dikirim form lonceng), ga aman -> Dashboard."""
    return get_safe_back_url(request.form.get("back")) or url_for("main.home")

@notifications_bp.post("/<int:notification_id>/open")
@login_required
def open_item(notification_id):
    """Klik notifikasi: tandain dibaca terus pindah ke tujuannya (kalau ada)."""
    notification = open_notification(get_current_user(), notification_id)
    if notification is None:
        abort(404)
    return redirect(get_safe_back_url(notification.target_url) or read_back_url())

@notifications_bp.post("/read-all")
@login_required
def read_all():
    """Tandain semua notifikasi dibaca."""
    mark_all_notification_read(get_current_user())
    return redirect(read_back_url())
