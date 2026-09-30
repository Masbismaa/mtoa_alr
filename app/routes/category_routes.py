"""Halaman kelola kategori, khusus admin."""
from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from app.schemas.category_schema import CategoryForm
from app.security.role_guard import admin_required
from app.services.category_service import (
    create_category,
    delete_category,
    get_category,
    is_default_category,
    list_category_summary,
    toggle_category_active,
    update_category,
)
from app.utils.exceptions import ValidationError

categories_bp = Blueprint("categories", __name__, url_prefix="/categories")

def get_user():
    """User asli (bukan proxy)."""
    return current_user._get_current_object()

def get_category_or_404(category_id):
    """Kategori ga ada -> 404."""
    category = get_category(category_id)
    if category is None:
        abort(404)
    return category

def build_form_data(form):
    """Isi form kategori jadi dict."""
    return {"name": form.name.data, "description": form.description.data}

def attach_error_list(form, error_list):
    """Error nama nempel di field-nya, sisanya jadi flash."""
    for error_dict in error_list:
        if error_dict["field"] == "name":
            form.name.errors.append(error_dict["message"])
        else:
            flash(error_dict["message"], "danger")

def render_category_form(form, page_title, form_action, is_name_locked=False):
    """Render form tambah/edit kategori."""
    return render_template(
        "pages/categories/form.html",
        form=form,
        page_title=page_title,
        form_action=form_action,
        is_name_locked=is_name_locked,
    )

@categories_bp.get("/")
@login_required
@admin_required
def index():
    """Tabel semua kategori + jumlah link-nya."""
    return render_template(
        "pages/categories/index.html",
        page_title="Categories",
        category_summary_list=list_category_summary(),
    )

@categories_bp.route("/new", methods=["GET", "POST"])
@login_required
@admin_required
def create():
    """Tambah kategori baru."""
    form = CategoryForm()
    if form.validate_on_submit():
        try:
            category = create_category(get_user(), build_form_data(form))
        except ValidationError as error:
            attach_error_list(form, error.error_list)
        else:
            flash(f'Kategori "{category.name}" berhasil ditambahkan', "success")
            return redirect(url_for("categories.index"))
    return render_category_form(form, "Tambah Kategori", url_for("categories.create"))

@categories_bp.route("/<int:category_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit(category_id):
    """Edit kategori. Nama kategori bawaan dikunci."""
    category = get_category_or_404(category_id)
    form = CategoryForm(obj=category)
    if form.validate_on_submit():
        try:
            update_category(get_user(), category, build_form_data(form))
        except ValidationError as error:
            attach_error_list(form, error.error_list)
        else:
            flash(f'Kategori "{category.name}" berhasil diperbarui', "success")
            return redirect(url_for("categories.index"))
    return render_category_form(
        form, "Edit Kategori", url_for("categories.edit", category_id=category.id),
        is_name_locked=is_default_category(category),
    )

@categories_bp.post("/<int:category_id>/toggle")
@login_required
@admin_required
def toggle(category_id):
    """Aktifin / nonaktifin kategori."""
    category = get_category_or_404(category_id)
    try:
        toggle_category_active(get_user(), category)
    except ValidationError as error:
        flash(error.error_list[0]["message"], "danger")
    else:
        status_text = "diaktifkan" if category.is_active else "dinonaktifkan"
        flash(f'Kategori "{category.name}" {status_text}', "success")
    return redirect(url_for("categories.index"))

@categories_bp.post("/<int:category_id>/delete")
@login_required
@admin_required
def delete(category_id):
    """Hapus kategori yg belum dipake (konfirmasinya di browser)."""
    category = get_category_or_404(category_id)
    category_name = category.name
    try:
        delete_category(get_user(), category)
    except ValidationError as error:
        flash(error.error_list[0]["message"], "danger")
    else:
        flash(f'Kategori "{category_name}" berhasil dihapus', "success")
    return redirect(url_for("categories.index"))