"""Route data link: tambah, detail, edit, hapus."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.schemas.access_entry_schema import AccessEntryForm
from app.security.access_policy import can_edit_entry, is_entry_owner
from app.services.access_entry_service import (
    build_category_option_list,
    create_access_entry,
    delete_access_entry,
    get_active_category_list,
    get_visible_entry,
    read_access_note,
    update_access_entry,
)
from app.utils.constants import CUSTOM_FIELD_MAX_COUNT
from app.utils.exceptions import ValidationError

entries_bp = Blueprint("entries", __name__, url_prefix="/entries")

# field form yg dikirim ke service (namanya sama persis)
FORM_FIELD_NAME_LIST = [
    "category_id", "title", "url", "address", "port",
    "username", "access_note", "description", "visibility",
]


def get_user():
    """Objek user asli (bukan proxy current_user)."""
    return current_user._get_current_object()


def get_entry_or_404(user, entry_id):
    """Ambil data yg boleh dilihat. Ga ada / Private orang lain -> 404 (biar ga ketauan ada)."""
    entry = get_visible_entry(user, entry_id)
    if entry is None:
        abort(404)
    return entry


def build_form_data_dict(form):
    """Ambil isi form jadi dict buat service."""
    return {field_name: getattr(form, field_name).data for field_name in FORM_FIELD_NAME_LIST}


def read_custom_field_pair_list():
    """Field tambahan dari form, urut sesuai tampilan: [(judul, isi), ...]."""
    label_list = request.form.getlist("custom_field_label")
    content_list = request.form.getlist("custom_field_content")
    return list(zip(label_list, content_list))


def attach_error_list(form, error_list):
    """Tempel error dari service ke field form-nya. Error lain dimunculin sebagai flash."""
    for error_dict in error_list:
        field_name = error_dict.get("field")
        if field_name in FORM_FIELD_NAME_LIST:
            getattr(form, field_name).errors.append(error_dict["message"])
        else:
            flash(error_dict["message"], "danger")


def render_entry_form(form, category_list, custom_field_pair_list, page_title, form_action, cancel_url, is_owner=True):
    """Render halaman form (dipake tambah & edit)."""
    form.category_id.choices = [(category.id, category.name) for category in category_list]
    return render_template(
        "pages/entries/form.html",
        form=form,
        page_title=page_title,
        form_action=form_action,
        cancel_url=cancel_url,
        is_owner=is_owner,
        category_option_list=build_category_option_list(category_list),
        custom_field_list=[{"field_label": label, "field_content": content} for label, content in custom_field_pair_list],
        custom_field_max_count=CUSTOM_FIELD_MAX_COUNT,
    )

@entries_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    """Tambah data link."""
    user = get_user()
    category_list = get_active_category_list()
    form = AccessEntryForm()
    form.category_id.choices = [(category.id, category.name) for category in category_list]
    custom_field_pair_list = read_custom_field_pair_list() if request.method == "POST" else []

    if form.validate_on_submit():
        try:
            entry = create_access_entry(user, build_form_data_dict(form), custom_field_pair_list)
        except ValidationError as error:
            attach_error_list(form, error.error_list)
        else:
            flash("Data link berhasil disimpan", "success")
            return redirect(url_for("entries.detail", entry_id=entry.id))

    return render_entry_form(
        form, category_list, custom_field_pair_list,
        page_title="Tambah Link", form_action=url_for("entries.create"), cancel_url=url_for("main.home"),
    )

@entries_bp.get("/<int:entry_id>")
@login_required
def detail(entry_id):
    """Detail data link."""
    user = get_user()
    entry = get_entry_or_404(user, entry_id)
    access_note, is_note_error = read_access_note(entry)
    if is_note_error:
        flash("Access note tidak bisa dibuka (kunci enkripsi berbeda atau data rusak)", "danger")
    return render_template(
        "pages/entries/detail.html",
        page_title="Detail Link",
        entry=entry,
        access_note=access_note,
        can_edit=can_edit_entry(user, entry),
    )

@entries_bp.route("/<int:entry_id>/edit", methods=["GET", "POST"])
@login_required
def edit(entry_id):
    """Edit data link (pemilik, atau admin untuk data Public)."""
    user = get_user()
    entry = get_entry_or_404(user, entry_id)
    if not can_edit_entry(user, entry):
        abort(403)

    category_list = get_active_category_list()
    if request.method == "GET":
        # isi form dari data yg ada
        form = AccessEntryForm(obj=entry)
        access_note, is_note_error = read_access_note(entry)
        form.access_note.data = access_note
        if is_note_error:
            flash("Access note lama tidak bisa dibuka, isi ulang kalau perlu", "warning")
        custom_field_pair_list = [(field.field_label, field.field_content) for field in entry.custom_field_list]
    else:
        form = AccessEntryForm()
        custom_field_pair_list = read_custom_field_pair_list()

    form.category_id.choices = [(category.id, category.name) for category in category_list]
    if form.validate_on_submit():
        try:
            update_access_entry(user, entry, build_form_data_dict(form), custom_field_pair_list)
        except ValidationError as error:
            attach_error_list(form, error.error_list)
        else:
            flash("Perubahan berhasil disimpan", "success")
            return redirect(url_for("entries.detail", entry_id=entry.id))

    return render_entry_form(
        form, category_list, custom_field_pair_list,
        page_title="Edit Link",
        form_action=url_for("entries.edit", entry_id=entry.id),
        cancel_url=url_for("entries.detail", entry_id=entry.id),
        is_owner=is_entry_owner(user, entry),
    )

@entries_bp.post("/<int:entry_id>/delete")
@login_required
def delete(entry_id):
    """Hapus data link (dialog konfirmasi muncul di sisi browser)."""
    user = get_user()
    entry = get_entry_or_404(user, entry_id)
    if not can_edit_entry(user, entry):
        abort(403)

    # judul disimpen dulu, abis dihapus objeknya udah ga bisa dibaca
    entry_title = entry.title
    delete_access_entry(user, entry)
    flash(f'Data "{entry_title}" berhasil dihapus', "success")
    return redirect(url_for("main.home"))