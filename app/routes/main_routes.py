"""Halaman utama setelah login (dashboard)."""
from flask import Blueprint, render_template
from flask_login import current_user, login_required

from app.services.access_entry_service import count_visible_entry_summary, list_visible_entries

main_bp = Blueprint("main", __name__)

# jumlah link terbaru yg tampil di dashboard (tabel lengkap + search)
DASHBOARD_ENTRY_LIMIT = 20

@main_bp.get("/")
@login_required
def home():
    """Dashboard: sapaan, angka ringkasan, dan tabel link terbaru."""
    user = current_user._get_current_object()
    summary_dict = count_visible_entry_summary(user)
    stat_card_list = [
        {"label": "Total Link", "value": summary_dict["total"], "icon": "link"},
        {"label": "Link Public", "value": summary_dict["public"], "icon": "globe"},
        {"label": "Link Private (milikmu)", "value": summary_dict["private"], "icon": "lock"},
        {"label": "Group", "value": "—", "icon": "group"},
    ]
    return render_template(
        "pages/home.html",
        page_title="Dashboard",
        stat_card_list=stat_card_list,
        entry_list=list_visible_entries(user, limit=DASHBOARD_ENTRY_LIMIT),
    )