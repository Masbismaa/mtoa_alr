"""Halaman utama setelah login (dashboard)."""
from flask import Blueprint, render_template, request
from flask_login import current_user, login_required
from app.services.access_entry_service import count_visible_entry_summary, get_active_category_list, search_visible_entries
from app.services.group_service import count_user_group
from app.utils.constants import DASHBOARD_PER_PAGE, VISIBILITY_LIST
from app.utils.query_helper import clean_keyword_arg, drop_empty_value ,parse_positive_int

main_bp = Blueprint("main", __name__)

def read_dashboard_filter():
    """Baca filter dari URL, nilai yg ngaco dicuekin aja."""
    visibility = request.args.get("visibility", "")
    return {
        "keyword": clean_keyword_arg(request.args.get("q")),
        "category_id": parse_positive_int(request.args.get("category_id")),
        "visibility": visibility if visibility in VISIBILITY_LIST else "",
        "page": parse_positive_int(request.args.get("page"), default=1),
    }

def build_stat_card_list(summary_dict, group_count):
    """Kartu ringkasan di atas dashboard."""
    return [
        {"label": "Total Link", "value": summary_dict["total"], "icon": "link"},
        {"label": "Link Public", "value": summary_dict["public"], "icon": "globe"},
        {"label": "Link Private (milikmu)", "value": summary_dict["private"], "icon": "lock"},
        {"label": "Group", "value": group_count, "icon": "group"},
    ]

@main_bp.get("/")
@login_required
def home():
    """Dashboard: ringkasan + tabel link dengan search, filter, dan pagination."""
    user = current_user._get_current_object()
    filter_dict = read_dashboard_filter()
    pagination = search_visible_entries(
        user,
        keyword=filter_dict["keyword"],
        category_id=filter_dict["category_id"],
        visibility=filter_dict["visibility"],
        page=filter_dict["page"],
        per_page=DASHBOARD_PER_PAGE,
    )
    # filter yg ikut kebawa pas pindah halaman (yg kosong ga usah)
    pagination_query_dict = drop_empty_value({
        "q": filter_dict["keyword"],
        "category_id": filter_dict["category_id"],
        "visibility": filter_dict["visibility"],
    })
    return render_template(
        "pages/home.html",
        page_title="Dashboard",
        stat_card_list=build_stat_card_list(count_visible_entry_summary(user), count_user_group(user)),
        pagination=pagination,
        pagination_query_dict=pagination_query_dict,
        filter_dict=filter_dict,
        category_list=get_active_category_list(),
    )