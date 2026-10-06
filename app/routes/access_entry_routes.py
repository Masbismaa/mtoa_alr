"""Route data link: tambah, detail, edit, hapus."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.schemas.access_entry_schema import AccessEntryForm
from app.security.access_policy import can_add_group_entry, can_edit_entry, is_entry_owner
from app.services.access_entry_service import (
    build_category_option_list,
    create_access_entry,
    delete_access_entry,
    get_active_category_list,
    get_form_category_list,
    get_visible_entry,
    read_access_note,
    update_access_entry,
)
from app.utils.constants import (
    ATTACHMENT_EXTENSION_LIST,
    ATTACHMENT_MAX_COUNT,
    ATTACHMENT_MAX_SIZE_BYTES,
    CUSTOM_FIELD_MAX_COUNT,
)
from app.utils.exceptions import ValidationError
from app.services.group_service import add_group_entry, get_member_group
from app.utils.query_helper import parse_positive_int
from app.utils.form_helper import attach_form_error_list, flash_error_list, read_form_data
from app.utils.request_helper import get_current_user

entries_bp = Blueprint("entries", __name__, url_prefix="/entries")

FORM_FIELD_NAME_LIST = [
    "category_id", "title", "url", "address", "port",
    "username", "access_note", "description", "visibility",
]

def get_entry_or_404(user, entry_id):
    """Ga ada / private orang lain -> 404."""
    entry = get_visible_entry(user, entry_id)
    if entry is None:
        abort(404)
    return entry

def read_custom_field_pair_list():
    """Field tambahan dari form: [(judul, isi), ...]."""
    return list(zip(request.form.getlist("custom_field_label"), request.form.getlist("custom_field_content")))

def attach_error_list(form, error_list):
    """Tempel error ke field form. Error lampiran dibalikin (tampil di kotak lampiran), sisanya jadi flash."""
    leftover_list = attach_form_error_list(form, error_list)
    flash_error_list([error_dict for error_dict in leftover_list if error_dict.get("field") != "attachments"])
    return [error_dict["message"] for error_dict in leftover_list if error_dict.get("field") == "attachments"]

def render_entry_form(form, category_list, custom_field_pair_list, page_title, form_action, cancel_url,
                      is_owner=True, entry=None, attachment_error_list=None, target_group=None):
    """Render form (dipake tambah & edit)."""
    form.category_id.choices = [(category.id, category.name) for category in category_list]
    existing_attachment_list = entry.attachment_list if entry else []
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
        existing_attachment_list=existing_attachment_list,
        attachment_error_list=attachment_error_list or [],
        attachment_max_count=ATTACHMENT_MAX_COUNT,
        attachment_max_size=ATTACHMENT_MAX_SIZE_BYTES,
        attachment_extension_list=ATTACHMENT_EXTENSION_LIST,
        target_group=target_group,
    )

@entries_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    """Tambah data link, bisa langsung masuk ke group kalau dibuka dari halaman group."""
    user = get_current_user()
    category_list = get_active_category_list()
    form = AccessEntryForm()
    form.category_id.choices = [(category.id, category.name) for category in category_list]
    custom_field_pair_list = read_custom_field_pair_list() if request.method == "POST" else []
    attachment_error_list = []
    if request.method == "GET":
        form.category_id.data = parse_positive_int(request.args.get("category_id"))
    # group tujuan, dicuekin kalau user bukan anggota aktif / belum diizinin nambah link
    group_id = parse_positive_int(request.values.get("group_id"))
    target_group = get_member_group(user, group_id) if group_id else None
    if target_group is not None and not can_add_group_entry(user, target_group):
        target_group = None
    if form.validate_on_submit():
        try:
            entry = create_access_entry(
                user, read_form_data(form, FORM_FIELD_NAME_LIST), custom_field_pair_list,
                upload_file_list=request.files.getlist("attachments"),
            )
        except ValidationError as error:
            attachment_error_list = attach_error_list(form, error.error_list)
        else:
            if target_group is not None:
                add_group_entry(user, target_group, entry.id)
                flash(f'Data link disimpan & masuk ke group "{target_group.name}"', "success")
                return redirect(url_for("groups.detail", group_id=target_group.id))
            flash("Data link berhasil disimpan", "success")
            return redirect(url_for("entries.detail", entry_id=entry.id))
    cancel_url = url_for("groups.detail", group_id=target_group.id) if target_group else url_for("main.home")
    return render_entry_form(
        form, category_list, custom_field_pair_list,
        page_title="Tambah Link", form_action=url_for("entries.create"), cancel_url=cancel_url,
        attachment_error_list=attachment_error_list, target_group=target_group,
    )

@entries_bp.get("/<int:entry_id>")
@login_required
def detail(entry_id):
    """Detail data link."""
    user = get_current_user()
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
    """Edit data link (pemilik, atau admin buat data Public)."""
    user = get_current_user()
    entry = get_entry_or_404(user, entry_id)
    if not can_edit_entry(user, entry):
        abort(403)

    category_list = get_form_category_list(entry.category)
    attachment_error_list = []
    if request.method == "GET":
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
            update_access_entry(
                user, entry, read_form_data(form, FORM_FIELD_NAME_LIST), custom_field_pair_list,
                upload_file_list=request.files.getlist("attachments"),
                delete_attachment_id_list=request.form.getlist("delete_attachment_id"),
            )
        except ValidationError as error:
            attachment_error_list = attach_error_list(form, error.error_list)
        else:
            flash("Perubahan berhasil disimpan", "success")
            return redirect(url_for("entries.detail", entry_id=entry.id))

    return render_entry_form(
        form, category_list, custom_field_pair_list,
        page_title="Edit Link",
        form_action=url_for("entries.edit", entry_id=entry.id),
        cancel_url=url_for("entries.detail", entry_id=entry.id),
        is_owner=is_entry_owner(user, entry),
        entry=entry,
        attachment_error_list=attachment_error_list,
    )

@entries_bp.post("/<int:entry_id>/delete")
@login_required
def delete(entry_id):
    """Hapus data link (konfirmasinya di browser)."""
    user = get_current_user()
    entry = get_entry_or_404(user, entry_id)
    if not can_edit_entry(user, entry):
        abort(403)

    entry_title = entry.title
    delete_access_entry(user, entry)
    flash(f'Data "{entry_title}" berhasil dihapus', "success")
    return redirect(url_for("main.home"))
