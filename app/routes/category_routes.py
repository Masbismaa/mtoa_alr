"""Halaman kategori: jelajah ala forum (semua user) + kelola kategori (admin)."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required
from app.extensions import limiter
from app.schemas.category_schema import CategoryForm
from app.security.role_guard import api_login_required, permission_required
from app.services.category_service import (
    build_category_label,
    build_forum_row_list,
    can_add_sub_category,
    can_manage_category,
    create_category,
    create_sub_category,
    delete_category,
    get_category,
    get_category_path_list,
    has_active_child_category,
    is_category_usable,
    is_default_category,
    list_category_summary,
    toggle_category_active,
    update_category,
    can_manage_category_master,
)
from app.services.entry_table_service import build_category_scope, build_entry_table_payload, build_scope_field_list
from app.utils.constants import MAX_CATEGORY_DEPTH, PERMISSION_MANAGE_CATEGORIES
from app.utils.exceptions import ValidationError
from app.utils.form_helper import attach_form_error_list, flash_error_list, read_form_data
from app.utils.request_helper import get_current_user
from app.utils.response_formatter import error_response, success_response

categories_bp = Blueprint("categories", __name__, url_prefix="/categories")

CATEGORY_FIELD_NAME_LIST = ["name", "description"]

def get_category_or_404(category_id):
    """Kategori ga ada -> 404."""
    category = get_category(category_id)
    if category is None:
        abort(404)
    return category

def get_visible_category_or_404(user, category_id):
    category = get_category_or_404(category_id)
    if not is_category_usable(category) and not can_manage_category_master(user):
        abort(404)
    return category

def build_back_url(user, parent_id):
    """Balik ke halaman induknya. Kategori utama balik ke tabel admin (atau Home buat user biasa)."""
    if parent_id is not None:
        return url_for("categories.browse", category_id=parent_id)
    return url_for("categories.index") if can_manage_category_master(user) else url_for("main.home")

def render_category_form(form, page_title, form_action, cancel_url, parent=None, is_name_locked=False, screen_title=None):
    """Render form tambah/edit kategori (utama maupun sub). screen_title = judul layar ala SAP (Create/Change)."""
    return render_template(
        "pages/categories/form.html",
        form=form,
        page_title=page_title,
        screen_title=screen_title,
        form_action=form_action,
        cancel_url=cancel_url,
        parent_label=build_category_label(parent) if parent is not None else None,
        is_name_locked=is_name_locked,
    )

@categories_bp.get("/")
@login_required
@permission_required(PERMISSION_MANAGE_CATEGORIES)
def index():
    """Tabel semua kategori (bentuk pohon) + jumlah link-nya."""
    return render_template(
        "pages/categories/index.html",
        page_title="Categories",
        category_summary_list=list_category_summary(),
        max_category_depth=MAX_CATEGORY_DEPTH,
    )

@categories_bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required(PERMISSION_MANAGE_CATEGORIES)
def create():
    """Tambah kategori utama, khusus admin."""
    form = CategoryForm()
    if form.validate_on_submit():
        try:
            category = create_category(get_current_user(), read_form_data(form, CATEGORY_FIELD_NAME_LIST))
        except ValidationError as error:
            flash_error_list(attach_form_error_list(form, error.error_list))
        else:
            flash(f'Kategori "{category.name}" berhasil ditambahkan', "success")
            return redirect(url_for("categories.index"))
    return render_category_form(form, "Tambah Kategori", url_for("categories.create"), url_for("categories.index"),
                                screen_title="Create Kategori")

@categories_bp.get("/<int:category_id>")
@login_required
def browse(category_id):
    """Isi satu kategori ala forum: sub-kategori + tabel link yg ada langsung di kategori ini (tabelnya React)."""
    user = get_current_user()
    category = get_visible_category_or_404(user, category_id)
    forum_row_list = build_forum_row_list(user, parent=category)
    scope = build_category_scope(category, has_sub_category=bool(forum_row_list))
    return render_template(
        "pages/categories/browse.html",
        page_title=category.name,
        category=category,
        path_list=get_category_path_list(category),
        forum_row_list=forum_row_list,
        selection_field_list=build_scope_field_list(scope),
        entry_table_payload=build_entry_table_payload(user, request.args, scope),
        can_add_sub=can_add_sub_category(category),
        can_manage=can_manage_category(user, category),
        is_default=is_default_category(category),
    )

@categories_bp.get("/<int:category_id>/table-data")
@api_login_required
@limiter.limit("120 per minute")
def table_data(category_id):
    """API tabel link di kategori ini (dipanggil React pas urutan/filter/halaman berubah). Parameter sama kayak halamannya."""
    user = get_current_user()
    category = get_category(category_id)
    if category is None or (not is_category_usable(category) and not can_manage_category_master(user)):
        return error_response("Kategori tidak ditemukan", 404)
    scope = build_category_scope(category, has_sub_category=has_active_child_category(category))
    return success_response(data=build_entry_table_payload(user, request.args, scope))

@categories_bp.route("/<int:category_id>/sub/new", methods=["GET", "POST"])
@login_required
def create_sub(category_id):
    """Tambah sub-kategori, semua user boleh (maksimal 4 tingkat)."""
    user = get_current_user()
    parent = get_visible_category_or_404(user, category_id)
    if not can_add_sub_category(parent):
        flash(f"Kategori ini udah tingkat paling dalam (maksimal {MAX_CATEGORY_DEPTH} tingkat)", "warning")
        return redirect(url_for("categories.browse", category_id=parent.id))

    form = CategoryForm()
    if form.validate_on_submit():
        try:
            category = create_sub_category(user, parent, read_form_data(form, CATEGORY_FIELD_NAME_LIST))
        except ValidationError as error:
            flash_error_list(attach_form_error_list(form, error.error_list))
        else:
            flash(f'Sub-kategori "{category.name}" berhasil ditambahkan', "success")
            return redirect(url_for("categories.browse", category_id=category.id))
    return render_category_form(
        form, "Tambah Sub-kategori", url_for("categories.create_sub", category_id=parent.id),
        url_for("categories.browse", category_id=parent.id), parent=parent, screen_title="Create Sub-kategori",
    )

@categories_bp.route("/<int:category_id>/edit", methods=["GET", "POST"])
@login_required
def edit(category_id):
    """Edit kategori: admin semua, user biasa cuma sub bikinannya. Nama kategori bawaan dikunci."""
    user = get_current_user()
    category = get_category_or_404(category_id)
    if not can_manage_category(user, category):
        abort(403)

    form = CategoryForm(obj=category)
    if form.validate_on_submit():
        try:
            update_category(user, category, read_form_data(form, CATEGORY_FIELD_NAME_LIST))
        except ValidationError as error:
            flash_error_list(attach_form_error_list(form, error.error_list))
        else:
            flash(f'Kategori "{category.name}" berhasil diperbarui', "success")
            return redirect(url_for("categories.browse", category_id=category.id))
    return render_category_form(
        form, "Edit Kategori", url_for("categories.edit", category_id=category.id),
        url_for("categories.browse", category_id=category.id),
        parent=category.parent, is_name_locked=is_default_category(category), screen_title=f"Change Kategori: {category.name}",
    )

@categories_bp.post("/<int:category_id>/toggle")
@login_required
@permission_required(PERMISSION_MANAGE_CATEGORIES)
def toggle(category_id):
    """Aktifin / nonaktifin kategori, khusus admin."""
    category = get_category_or_404(category_id)
    try:
        toggle_category_active(get_current_user(), category)
    except ValidationError as error:
        flash_error_list(error.error_list)
    else:
        status_text = "diaktifkan" if category.is_active else "dinonaktifkan"
        flash(f'Kategori "{category.name}" {status_text}', "success")
    return redirect(url_for("categories.index"))

@categories_bp.post("/<int:category_id>/delete")
@login_required
def delete(category_id):
    """Hapus kategori kosong (konfirmasinya di browser). Admin, atau pembuat sub-kategori itu."""
    user = get_current_user()
    category = get_category_or_404(category_id)
    if not can_manage_category(user, category):
        abort(403)

    category_name = category.name
    parent_id = category.parent_id
    try:
        delete_category(user, category)
    except ValidationError as error:
        flash_error_list(error.error_list)
        return redirect(url_for("categories.browse", category_id=category.id))
    flash(f'Kategori "{category_name}" berhasil dihapus', "success")
    return redirect(build_back_url(user, parent_id))
