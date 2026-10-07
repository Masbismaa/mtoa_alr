"""Halaman kelola user, khusus admin."""
from urllib.parse import urlencode
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required
from app.extensions import limiter
from app.security.role_guard import admin_required
from app.schemas.selection_schema import USER_FIELD_LIST, USER_FILTER_KEY_LIST, read_user_selection
from app.schemas.table_schema import TABLE_USER
from app.services.preference_service import get_table_layout
from app.services.user_service import (
    build_delete_preview,
    build_user_summary,
    delete_user_account,
    get_permission_key_list,
    get_user,
    get_user_status,
    search_users,
    set_user_permissions,
    toggle_user_active,
    unlock_user,
)
from app.utils.constants import PERMISSION_INFO_DICT, ROLE_ADMIN, PER_PAGE
from app.utils.data_table import build_table_view
from app.utils.exceptions import ValidationError
from app.utils.query_helper import parse_positive_int
from app.utils.selection import build_selection_query_dict
from app.utils.form_helper import flash_error_list
from app.utils.request_helper import get_current_user

users_bp = Blueprint("users", __name__, url_prefix="/users")

def build_back_param_dict():
    """Kriteria yg lagi kepake di tabel, dikasih awalan back_ buat dibawa ke halaman/form aksi (bisa banyak nilai)."""
    return {f"back_{key}": request.args.getlist(key) for key in USER_FILTER_KEY_LIST if request.args.getlist(key)}

@users_bp.get("/")
@login_required
@admin_required
def index():
    """Tabel semua user + Kriteria Pencarian (Select Screen) + pagination."""
    selection = read_user_selection(request.args)
    table_view = build_table_view(TABLE_USER, request.args, get_table_layout(get_current_user(), TABLE_USER), field_list=USER_FIELD_LIST)
    pagination = search_users(
        keyword=selection["keyword"],
        selection=selection,
        sort=table_view["sort"],
        page=parse_positive_int(request.args.get("page"), default=1),
        per_page=PER_PAGE,
    )
    return render_template(
        "pages/users/index.html",
        page_title="Users",
        pagination=pagination,
        user_row_list=[
            {"user": user, "status": get_user_status(user), "permission_key_list": get_permission_key_list(user)}
            for user in pagination.items
        ],
        pagination_query_dict=build_selection_query_dict(request.args, USER_FIELD_LIST),
        selection_field_list=USER_FIELD_LIST,
        keyword=selection["keyword"],
        summary_dict=build_user_summary(),
        permission_info_dict=PERMISSION_INFO_DICT,
        back_param_dict=build_back_param_dict(),
        table_view=table_view,
    )

def get_target_user_or_404(user_id):
    """User yg mau diubah, ga ada / udah dihapus -> 404."""
    target = get_user(user_id)
    if target is None or target.deleted_at is not None:
        abort(404)
    return target

def redirect_if_admin(target, message):
    """Akun admin ga bisa diatur dari panel, balik ke tabel + kasih info. None kalau bukan admin."""
    if target.role != ROLE_ADMIN:
        return None
    flash(message, "info")
    return redirect(url_for("users.index"))

def build_back_url():
    """Balik ke tabel user dgn kriteria yg tadi lagi kepake (dikirim lewat input hidden back_*)."""
    filter_dict = {key: request.values.getlist(f"back_{key}") for key in USER_FILTER_KEY_LIST}
    filter_dict = {key: value_list for key, value_list in filter_dict.items() if value_list}
    return url_for("users.index") + (f"?{urlencode(filter_dict, doseq=True)}" if filter_dict else "")

def run_user_action(action_function, success_message, *arg_list):
    """Jalanin aksi ke user + flash hasilnya, terus balik ke tabel (biar ga nulis try/except berulang)."""
    try:
        action_function(get_current_user(), *arg_list)
    except ValidationError as error:
        flash_error_list(error.error_list)
    else:
        flash(success_message, "success")
    return redirect(build_back_url())

@users_bp.route("/<int:user_id>/access", methods=["GET", "POST"])
@login_required
@admin_required
def access(user_id):
    """Atur akses user: centang akses yg dikasih, hapus centang buat nyabut."""
    target = get_target_user_or_404(user_id)
    admin_redirect = redirect_if_admin(target, "Admin otomatis punya semua akses, perubahan admin lewat command")
    if admin_redirect:
        return admin_redirect

    if request.method == "POST":
        try:
            set_user_permissions(get_current_user(), target, request.form.getlist("permission"))
        except ValidationError as error:
            flash_error_list(error.error_list)
        else:
            flash(f"Akses {target.full_name} sudah disimpan", "success")
            return redirect(build_back_url())

    return render_template(
        "pages/users/access.html",
        page_title="Atur Akses",
        target=target,
        owned_key_list=get_permission_key_list(target),
        permission_info_dict=PERMISSION_INFO_DICT,
        back_url=build_back_url(),
    )

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

@users_bp.route("/<int:user_id>/delete", methods=["GET", "POST"])
@login_required
@admin_required
@limiter.limit("5 per minute", methods=["POST"])
def delete(user_id):
    """Hapus akun: tampilin dampaknya dulu, admin ngetik ulang email buat konfirmasi."""
    target = get_target_user_or_404(user_id)
    admin_redirect = redirect_if_admin(target, "Akun admin tidak bisa dihapus dari panel")
    if admin_redirect:
        return admin_redirect

    if request.method == "POST":
        full_name = target.full_name
        try:
            delete_user_account(get_current_user(), target, request.form.get("confirm_email"))
        except ValidationError as error:
            flash_error_list(error.error_list)
        else:
            flash(f"Akun {full_name} sudah dihapus", "success")
            return redirect(build_back_url())

    return render_template(
        "pages/users/delete.html",
        page_title="Hapus Akun",
        target=target,
        delete_preview_dict=build_delete_preview(target),
        back_url=build_back_url(),
    )
