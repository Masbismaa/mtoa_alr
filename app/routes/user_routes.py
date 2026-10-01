"""Halaman kelola user, khusus admin."""
from flask import Blueprint, render_template, request
from flask_login import login_required
from app.security.role_guard import admin_required
from app.services.user_service import build_user_summary, get_user_status, search_users
from app.utils.constants import ROLE_LABEL_DICT, USER_PER_PAGE, USER_STATUS_LABEL_DICT
from app.utils.query_helper import clean_keyword_arg, drop_empty_value, parse_positive_int

users_bp = Blueprint("users", __name__, url_prefix="/users")

def read_user_filter():
    """Baca filter dari URL, nilai yg ngaco dicuekin aja."""
    role = request.args.get("role", "")
    status = request.args.get("status", "")
    return {
        "keyword": clean_keyword_arg(request.args.get("q")),
        "role": role if role in ROLE_LABEL_DICT else "",
        "status": status if status in USER_STATUS_LABEL_DICT else "",
        "page": parse_positive_int(request.args.get("page"), default=1),
    }

@users_bp.get("/")
@login_required
@admin_required
def index():
    """Tabel semua user + search, filter role & status, pagination."""
    filter_dict = read_user_filter()
    pagination = search_users(
        keyword=filter_dict["keyword"],
        role=filter_dict["role"],
        status=filter_dict["status"],
        page=filter_dict["page"],
        per_page=USER_PER_PAGE,
    )
    return render_template(
        "pages/users/index.html",
        page_title="Users",
        pagination=pagination,
        user_row_list=[{"user": user, "status": get_user_status(user)} for user in pagination.items],
        pagination_query_dict=drop_empty_value({
            "q": filter_dict["keyword"],
            "role": filter_dict["role"],
            "status": filter_dict["status"],
        }),
        filter_dict=filter_dict,
        summary_dict=build_user_summary(),
        role_label_dict=ROLE_LABEL_DICT,
        status_label_dict=USER_STATUS_LABEL_DICT,
    )