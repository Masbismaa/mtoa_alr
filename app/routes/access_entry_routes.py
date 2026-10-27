"""Route data link: Daftar Link (kriteria + tabel), tambah, detail, edit, hapus."""
from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import login_required

from app.extensions import limiter
from app.schemas.access_entry_schema import AccessEntryForm
from app.security.access_policy import can_add_group_entry, can_edit_entry, is_admin, is_entry_owner
from app.security.role_guard import api_login_required
from app.services.access_entry_service import (
    build_category_option_list,
    create_access_entry,
    delete_access_entry,
    delete_access_entry_list,
    get_form_category_list,
    get_visible_entry,
    is_favorite_entry,
    read_access_note,
    toggle_archive,
    toggle_favorite,
    update_access_entry,
)
from app.services.audit_service import list_entity_history
from app.services.category_service import list_usable_category
from app.services.import_service import import_entries
from app.services.import_template_service import build_import_template
from app.services.entry_table_service import build_entry_table_payload, build_index_scope, build_scope_field_list
from app.utils.constants import (
    ATTACHMENT_EXTENSION_LIST,
    ATTACHMENT_MAX_COUNT,
    ATTACHMENT_MAX_SIZE_BYTES,
    BULK_DELETE_MAX_COUNT,
    CUSTOM_FIELD_MAX_COUNT,
    IMPORT_MAX_ROW_COUNT,
)
from app.utils.exceptions import PermissionDeniedError, ValidationError
from app.utils.response_formatter import error_response, success_response
from app.services.group_service import add_group_entry, get_member_group
from app.utils.query_helper import parse_positive_int
from app.utils.form_helper import attach_form_error_list, flash_error_list, read_form_data
from app.utils.request_helper import get_current_user
from app.utils.selection import build_selection_query_dict
from app.utils.url_helper import get_safe_back_url

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

def read_back_url():
    """Alamat tabel asal (?back=) yg dibawa terus lewat detail -> edit -> simpan/batal/hapus. Ga aman -> None."""
    return get_safe_back_url(request.values.get("back"))

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
    """Render form (dipake tambah & edit). Judul layar ala SAP: Create (tambah) / Change (edit)."""
    form.category_id.choices = [(category.id, category.name) for category in category_list]
    existing_attachment_list = entry.attachment_list if entry else []
    return render_template(
        "pages/entries/form.html",
        form=form,
        page_title=page_title,
        screen_title=f"Change Access Link: {entry.title}" if entry else "Create Access Link",
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

@entries_bp.get("/")
@login_required
def index():
    """Daftar Link ala Select Screen SAP: awalnya cuma Kriteria Pencarian, tabel (ALV, React) baru muncul abis Jalankan."""
    user = get_current_user()
    scope = build_index_scope()
    field_list = build_scope_field_list(scope)
    # belum Jalankan (ga ada kriteria sama sekali) -> tabel ga ditampilin, query-nya juga ga dijalanin
    is_run = bool(build_selection_query_dict(request.args, field_list))
    return render_template(
        "pages/entries/index.html",
        page_title="Link List",
        selection_field_list=field_list,
        entry_table_payload=build_entry_table_payload(user, request.args, scope) if is_run else None,
    )

@entries_bp.get("/table-data")
@api_login_required
@limiter.limit("120 per minute")
def table_data():
    """API tabel Daftar Link (dipanggil React pas urutan/filter/halaman berubah). Parameter sama kayak halamannya."""
    return success_response(data=build_entry_table_payload(get_current_user(), request.args, build_index_scope()))

@entries_bp.post("/bulk-delete")
@api_login_required
@limiter.limit("20 per minute")
def bulk_delete():
    """Hapus banyak link dari tabel (centang baris), khusus admin. Body JSON: {"entry_id_list": [1, 2, ...]}."""
    user = get_current_user()
    if not is_admin(user):
        return error_response("Only admins can delete several links at once", 403)
    payload = request.get_json(silent=True)
    raw_id_list = payload.get("entry_id_list") if isinstance(payload, dict) else None
    if not isinstance(raw_id_list, list) or not raw_id_list or len(raw_id_list) > BULK_DELETE_MAX_COUNT:
        return error_response(f"Select 1-{BULK_DELETE_MAX_COUNT} links to delete", 400)
    entry_id_list = [parse_positive_int(value) for value in raw_id_list]
    if None in entry_id_list:
        return error_response("Invalid link id", 400)
    deleted_count = delete_access_entry_list(user, set(entry_id_list))
    return success_response(data={"deleted_count": deleted_count}, message=f"{deleted_count} links deleted")

@entries_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    """Tambah data link, bisa langsung masuk ke group kalau dibuka dari halaman group."""
    user = get_current_user()
    category_list = list_usable_category()
    form = AccessEntryForm()
    form.category_id.choices = [(category.id, category.name) for category in category_list]
    custom_field_pair_list = read_custom_field_pair_list() if request.method == "POST" else []
    attachment_error_list = []
    back_url = read_back_url()
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
                # link-nya udah kesimpen duluan. Kalau masuk ke group gagal (misal izin nambah link baru aja dicabut),
                # kasih tau jelas & arahin ke link-nya, biar user ga bikin link yg sama dua kali
                try:
                    add_group_entry(user, target_group, entry.id)
                except (PermissionDeniedError, ValidationError) as error:
                    reason = error.error_list[0]["message"] if isinstance(error, ValidationError) else str(error)
                    flash(f'Link saved, but it could not be added to group "{target_group.name}": {reason}', "warning")
                    return redirect(url_for("entries.detail", entry_id=entry.id, back=back_url))
                flash(f'Link saved & added to group "{target_group.name}"', "success")
                return redirect(url_for("groups.detail", group_id=target_group.id))
            flash("Link saved", "success")
            return redirect(url_for("entries.detail", entry_id=entry.id, back=back_url))
    if target_group is not None:
        cancel_url = url_for("groups.detail", group_id=target_group.id)
    else:
        cancel_url = back_url or url_for("entries.index")
    return render_entry_form(
        form, category_list, custom_field_pair_list,
        page_title="Add Link", form_action=url_for("entries.create", back=back_url), cancel_url=cancel_url,
        attachment_error_list=attachment_error_list, target_group=target_group,
    )

@entries_bp.route("/import", methods=["GET", "POST"])
@login_required
@limiter.limit("10 per minute", methods=["POST"])
def import_page():
    """Import link dari Excel (template). Ada 1 baris salah -> ga ada yg disimpen, error per baris ditampilin."""
    error_list = []
    if request.method == "POST":
        upload_file = request.files.get("import_file")
        if upload_file is None or not upload_file.filename:
            error_list = ["Choose the Excel file to import"]
        else:
            try:
                imported_count = import_entries(get_current_user(), upload_file)
            except ValidationError as error:
                error_list = [error_dict["message"] for error_dict in error.error_list]
            else:
                flash(f"{imported_count} links imported", "success")
                return redirect(url_for("entries.index", run=1))
    return render_template(
        "pages/entries/import.html",
        page_title="Import Links",
        error_list=error_list,
        import_max_row_count=IMPORT_MAX_ROW_COUNT,
    )

@entries_bp.get("/import/template")
@login_required
def import_template():
    """Download template Excel buat import (kolom + daftar kategori yg bisa dipake)."""
    return send_file(build_import_template(), as_attachment=True, download_name="ALR_import_template.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", max_age=0)

@entries_bp.get("/<int:entry_id>")
@login_required
def detail(entry_id):
    """Detail data link."""
    user = get_current_user()
    entry = get_entry_or_404(user, entry_id)
    is_editable = can_edit_entry(user, entry)
    # isi access note sengaja ga ditempel di HTML: diambil lewat reveal_access_note_api pas user klik Show/Copy
    return render_template(
        "pages/entries/detail.html",
        page_title="Detail Link",
        entry=entry,
        has_access_note=entry.encrypted_access_note is not None,
        can_edit=is_editable,
        is_favorite=is_favorite_entry(user, entry),
        # riwayat link cuma buat yg boleh ngubah link ini
        history_list=list_entity_history("access_entries", entry.id) if is_editable else [],
        # balik ke tabel asal (Daftar Link/kategori/group) lengkap sama filter & urutannya
        back_url=read_back_url(),
    )

@entries_bp.post("/<int:entry_id>/access-note")
@api_login_required
@limiter.limit("30 per minute")
def reveal_access_note_api(entry_id):
    """Isi access note buat tombol Show/Copy di detail."""
    user = get_current_user()
    entry = get_visible_entry(user, entry_id)
    if entry is None:
        return error_response("Link not found", 404)
    access_note, is_note_error = read_access_note(entry)
    if is_note_error:
        return error_response("The access note can't be opened (different encryption key or corrupted data)", 500)
    if not access_note:
        return error_response("This link has no access note", 404)
    return success_response(data={"access_note": access_note})

@entries_bp.post("/<int:entry_id>/favorite")
@login_required
def favorite(entry_id):
    """Tandain / lepas bintang (favorit). Balik ke detail, konteks tabel asalnya tetep kebawa."""
    user = get_current_user()
    entry = get_entry_or_404(user, entry_id)
    is_now_favorite = toggle_favorite(user, entry)
    flash("Added to Favorites" if is_now_favorite else "Removed from Favorites", "success")
    return redirect(url_for("entries.detail", entry_id=entry.id, back=read_back_url()))

@entries_bp.post("/<int:entry_id>/archive")
@login_required
def archive(entry_id):
    """Pindahin ke arsip / balikin (yg boleh edit). Balik ke detail, konteks tabel asalnya tetep kebawa."""
    user = get_current_user()
    entry = get_entry_or_404(user, entry_id)
    if not can_edit_entry(user, entry):
        abort(403)
    is_now_archived = toggle_archive(user, entry)
    flash("Moved to Archive" if is_now_archived else "Restored from Archive", "success")
    return redirect(url_for("entries.detail", entry_id=entry.id, back=read_back_url()))

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
    back_url = read_back_url()
    if request.method == "GET":
        form = AccessEntryForm(obj=entry)
        access_note, is_note_error = read_access_note(entry)
        form.access_note.data = access_note
        if is_note_error:
            flash("The old access note can't be opened; fill it in again if needed", "warning")
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
            flash("Changes saved", "success")
            return redirect(url_for("entries.detail", entry_id=entry.id, back=back_url))

    # konteks daftar asal ikut kebawa: Simpan & Batal balik ke detail yg masih inget tabel asalnya
    return render_entry_form(
        form, category_list, custom_field_pair_list,
        page_title="Edit Link",
        form_action=url_for("entries.edit", entry_id=entry.id, back=back_url),
        cancel_url=url_for("entries.detail", entry_id=entry.id, back=back_url),
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
    flash(f'Link "{entry_title}" deleted', "success")
    # balik ke tabel asal (filter & urutan tetep), kalau ga ada ke Daftar Link
    return redirect(read_back_url() or url_for("entries.index"))
