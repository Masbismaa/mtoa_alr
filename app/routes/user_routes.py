"""Halaman kelola user, khusus admin."""
from urllib.parse import urlencode
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.security.role_guard import admin_required
from app.services.user_service import (
    build_user_summary,
    change_user_role,
    get_user,
    get_user_status,
    search_users,
    toggle_user_active,
    unlock_user,
)
from app.utils.constants import ROLE_LABEL_DICT, USER_PER_PAGE, USER_STATUS_LABEL_DICT
from app.utils.exceptions import ValidationError
from app.utils.query_helper import clean_keyword_arg, drop_empty_value, parse_positive_int

users_bp = Blueprint("users", __name__, url_prefix="/users")

# filter tabel yg ikut dibawa balik setelah ubah akun
USER_FILTER_KEY_LIST = ["q", "role", "status", "page"]

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

def get_target_user_or_404(user_id):
    """User yg mau diubah, ga ada -> 404."""
    target = get_user(user_id)
    if target is None:
        abort(404)
    return target

def build_back_url():
    """Balik ke tabel user dgn filter yg tadi lagi kepake (dikirim lewat input hidden)."""
    filter_dict = drop_empty_value({key: request.form.get(f"back_{key}", "") for key in USER_FILTER_KEY_LIST})
    return url_for("users.index") + (f"?{urlencode(filter_dict)}" if filter_dict else "")

def run_user_action(action_function, success_message, *arg_list):
    """Jalanin aksi ke user + flash hasilnya, terus balik ke tabel (biar ga nulis try/except berulang)."""
    try:
        action_function(current_user._get_current_object(), *arg_list)
    except ValidationError as error:
        flash(error.error_list[0]["message"], "danger")
    else:
        flash(success_message, "success")
    return redirect(build_back_url())

@users_bp.post("/<int:user_id>/role")
@login_required
@admin_required
def change_role(user_id):
    """Ganti role user."""
    target = get_target_user_or_404(user_id)
    new_role = request.form.get("role", "")
    role_label = ROLE_LABEL_DICT.get(new_role, new_role)
    return run_user_action(change_user_role, f"Role {target.full_name} sekarang {role_label}", target, new_role)

@users_bp.post("/<int:user_id>/toggle-active")
@login_required
@admin_required
def toggle_active(user_id):
    """Aktifin / nonaktifin akun."""
    target = get_target_user_or_404(user_id)
    status_text = "dinonaktifkan" if target.is_active else "diaktifkan lagi"
    return run_user_action(toggle_user_active, f"Akun {target.full_name} {status_text}", target)

@users_bp.post("/<int:user_id>/unlock")
@login_required
@admin_required
def unlock(user_id):
    """Buka kunci akun yg lagi terkunci."""
    target = get_target_user_or_404(user_id)
    return run_user_action(unlock_user, f"Kunci akun {target.full_name} sudah dibuka", target)