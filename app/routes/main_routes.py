"""Halaman dashboard."""
from flask import Blueprint, render_template
from flask_login import login_required

main_bp = Blueprint("main", __name__)

# kartu ringkasan sementara
DASHBOARD_STAT_CARD_LIST = [
    {"label": "Total Link", "value": "—", "icon": "link"},
    {"label": "Link Public", "value": "—", "icon": "globe"},
    {"label": "Link Private", "value": "—", "icon": "lock"},
    {"label": "Group", "value": "—", "icon": "group"},
]

@main_bp.get("/")
@login_required
def home():
    """Dashboard versi awal: sapaan + kartu ringkasan."""
    return render_template(
        "pages/home.html",
        page_title="Dashboard",
        stat_card_list=DASHBOARD_STAT_CARD_LIST,
    )