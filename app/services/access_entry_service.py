"""Logika CRUD Access Entry. Route tinggal manggil fungsi di sini."""
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models import AccessEntry, AccessEntryField, Category
from app.security.access_policy import build_visible_entry_filter, can_edit_entry, is_entry_owner
from app.security.encryption_service import decrypt_credential, encrypt_credential
from app.services.attachment_service import (
    pick_entry_attachment_list,
    prepare_upload_list,
    remove_file_path_list,
    remove_stored_file_list,
    store_prepared_attachment_list,
)
from app.services.audit_service import log_audit
from app.services.category_service import (
    build_category_label,
    get_category,
    get_root_category,
    is_category_usable,
    list_descendant_id,
    list_usable_category,
)
from app.utils.constants import (
    AUDIT_ACTION_CREATE,
    AUDIT_ACTION_DELETE,
    AUDIT_ACTION_UPDATE,
    CATEGORY_FIELD_RULE_DICT,
    CATEGORY_SPECIFIC_FIELD_LIST,
    CUSTOM_FIELD_MAX_COUNT,
    DEFAULT_CATEGORY_FIELD_RULE,
    MAX_ACCESS_NOTE_LENGTH,
    MAX_FIELD_LABEL_LENGTH,
    MAX_RICH_TEXT_LENGTH,
    MAX_TITLE_LENGTH,
    MAX_USERNAME_LENGTH,
    VISIBILITY_LIST,
    VISIBILITY_PRIVATE,
    VISIBILITY_PUBLIC,
    DASHBOARD_PER_PAGE,
    MAX_SEARCH_KEYWORD_LENGTH,
    EXPORT_MAX_ROW_COUNT,
)
from app.utils.exceptions import InvalidCredentialError, PermissionDeniedError, ValidationError, build_error
from app.utils.sanitizer import get_plain_text, sanitize_rich_text, sanitize_text
from app.utils.url_helper import normalize_address, normalize_url, parse_port
from app.utils.query_helper import escape_like_pattern
from app.utils.query_helper import build_keyword_filter

AUDIT_ENTITY_TYPE = "access_entries"

# kolom yg langsung disalin dari data bersih ke model
ENTRY_COLUMN_FIELD_LIST = ["category_id", "title", "url", "address", "port", "username", "description", "visibility"]

# fungsi validasi tiap field khusus kategori
FIELD_NORMALIZER_DICT = {"url": normalize_url, "address": normalize_address, "port": parse_port}

# KATEGORI
def get_category_rule(category):
    """Aturan field ngikut kategori utamanya (Web › SAP tetep wajib URL kayak Web)."""
    return CATEGORY_FIELD_RULE_DICT.get(get_root_category(category).name, DEFAULT_CATEGORY_FIELD_RULE)

def get_active_category_list():
    """Kategori yg bisa dipilih (dia & induknya aktif), urut kayak pohon."""
    return list_usable_category()

def get_form_category_list(current_category=None):
    """Pilihan kategori di form. Pas edit, kategori lama tetep ikut walau udah dinonaktifin admin."""
    category_list = list(get_active_category_list())
    if current_category is not None and not is_category_usable(current_category):
        category_list.append(current_category)
    return category_list

def get_category_from_id(raw_category_id, current_category_id=None):
    """Ambil kategori dari id, None kalau ga valid. Kategori nonaktif cuma boleh kalau itu kategori lama data-nya."""
    try:
        category_id = int(raw_category_id)
    except (TypeError, ValueError):
        return None
    category = db.session.get(Category, category_id)
    if category is None:
        return None
    if not is_category_usable(category) and category.id != current_category_id:
        return None
    return category

def build_category_option_list(category_list):
    """Data dropdown kategori + aturan field-nya (dipake JS)."""
    option_list = []
    for category in category_list:
        rule = get_category_rule(category)
        option_list.append({
            "id": category.id,
            "name": build_category_label(category),
            "field_list": ",".join(rule["field_list"]),
            "required_field_list": ",".join(rule["required_field_list"]),
            "has_custom_field": "true" if rule["has_custom_field"] else "false",
        })
    return option_list

# VALIDASI
def validate_entry_data(data_dict, current_category_id=None):
    """Cek & bersihin data utama. Return (clean_dict, category, error_list)."""
    category = get_category_from_id(data_dict.get("category_id"), current_category_id)
    if category is None:
        return {}, None, [build_error("category_id", "Kategori tidak valid")]

    rule = get_category_rule(category)
    error_list = []
    clean_dict = {"category_id": category.id}

    clean_dict["title"] = sanitize_text(data_dict.get("title"), max_length=MAX_TITLE_LENGTH)
    if not clean_dict["title"]:
        error_list.append(build_error("title", "Judul wajib diisi"))

    # field yg ga dipake kategori ini dikosongin
    for field_name in CATEGORY_SPECIFIC_FIELD_LIST:
        clean_dict[field_name] = None
        if field_name not in rule["field_list"]:
            continue
        raw_value = data_dict.get(field_name)
        is_empty = raw_value is None or str(raw_value).strip() == ""
        if is_empty and field_name not in rule["required_field_list"]:
            continue
        try:
            clean_dict[field_name] = FIELD_NORMALIZER_DICT[field_name](raw_value)
        except ValueError as error:
            error_list.append(build_error(field_name, str(error)))

    clean_dict["username"] = sanitize_text(data_dict.get("username"), max_length=MAX_USERNAME_LENGTH) or None

    raw_access_note = data_dict.get("access_note") or ""
    if len(raw_access_note) > MAX_ACCESS_NOTE_LENGTH:
        error_list.append(build_error("access_note", f"Access note maksimal {MAX_ACCESS_NOTE_LENGTH} karakter"))
    # ga di-sanitize biar password utuh, nanti dienkripsi
    clean_dict["access_note"] = raw_access_note if raw_access_note.strip() else None

    clean_dict["description"] = sanitize_text(data_dict.get("description")) or None

    visibility = data_dict.get("visibility")
    if visibility not in VISIBILITY_LIST:
        error_list.append(build_error("visibility", "Pilih Public atau Private"))
    clean_dict["visibility"] = visibility

    return clean_dict, category, error_list

def validate_custom_field_list(category, custom_field_pair_list):
    """Cek field tambahan (khusus kategori General). Return (clean_list, error_list)."""
    rule = get_category_rule(category)
    if not rule["has_custom_field"]:
        return [], []

    pair_list = list(custom_field_pair_list or [])
    if len(pair_list) > CUSTOM_FIELD_MAX_COUNT:
        return [], [build_error("custom_field", f"Maksimal {CUSTOM_FIELD_MAX_COUNT} field tambahan")]

    clean_list = []
    error_list = []
    for field_number, (raw_label, raw_content) in enumerate(pair_list, start=1):
        clean_label = sanitize_text(raw_label, max_length=MAX_FIELD_LABEL_LENGTH)
        clean_content = sanitize_rich_text(raw_content)

        if not clean_label:
            error_list.append(build_error("custom_field", f"Judul field ke-{field_number} wajib diisi"))
        if len(raw_content or "") > MAX_RICH_TEXT_LENGTH:
            error_list.append(build_error("custom_field", f"Isi field ke-{field_number} kepanjangan"))
        elif not get_plain_text(clean_content):
            error_list.append(build_error("custom_field", f"Isi field ke-{field_number} wajib diisi"))

        clean_list.append({"field_label": clean_label, "field_content": clean_content, "sort_order": field_number})
    return clean_list, error_list

def find_duplicate_entry(user, clean_dict, exclude_entry_id=None):
    """Cari data dgn URL / Address+Port sama, cuma di data sendiri + Public. Return (field, entry)."""
    base_query = db.select(AccessEntry).where(build_visible_entry_filter(user))
    if exclude_entry_id is not None:
        base_query = base_query.where(AccessEntry.id != exclude_entry_id)

    if clean_dict.get("url"):
        duplicate_entry = db.session.execute(
            base_query.where(AccessEntry.url == clean_dict["url"]).limit(1)
        ).scalar_one_or_none()
        if duplicate_entry is not None:
            return "url", duplicate_entry

    if clean_dict.get("address"):
        port_value = clean_dict.get("port")
        port_condition = AccessEntry.port.is_(None) if port_value is None else AccessEntry.port == port_value
        duplicate_entry = db.session.execute(
            base_query.where(AccessEntry.address == clean_dict["address"], port_condition).limit(1)
        ).scalar_one_or_none()
        if duplicate_entry is not None:
            return "address", duplicate_entry

    return None, None

def prepare_entry_data(user, data_dict, custom_field_pair_list, upload_file_list=None,
                       existing_attachment_count=0, exclude_entry_id=None, current_category_id=None):
    """Semua validasi jadi satu (create & update). Return (clean_dict, custom_list, upload_list)."""
    clean_dict, category, error_list = validate_entry_data(data_dict, current_category_id)

    clean_custom_field_list = []
    if category is not None:
        clean_custom_field_list, custom_error_list = validate_custom_field_list(category, custom_field_pair_list)
        error_list.extend(custom_error_list)

    # lampiran dicek sekalian biar semua error keluar barengan
    prepared_upload_list, upload_error_list = prepare_upload_list(upload_file_list, existing_attachment_count)
    error_list.extend(upload_error_list)

    # cek duplikat kalau yg lain udah beres aja (hemat query)
    if not error_list:
        duplicate_field, duplicate_entry = find_duplicate_entry(user, clean_dict, exclude_entry_id)
        if duplicate_entry is not None:
            error_list.append(build_error(duplicate_field, f'Sudah terdaftar di data "{duplicate_entry.title}"'))

    if error_list:
        raise ValidationError(error_list)
    return clean_dict, clean_custom_field_list, prepared_upload_list


# ================= SIMPAN =================

# SIMPAN
def apply_entry_data(entry, clean_dict, clean_custom_field_list):
    """Salin data bersih ke entry (access note dienkripsi, field tambahan diganti semua)."""
    for field_name in ENTRY_COLUMN_FIELD_LIST:
        setattr(entry, field_name, clean_dict[field_name])
    entry.encrypted_access_note = encrypt_credential(clean_dict["access_note"])
    entry.custom_field_list = [AccessEntryField(**field_dict) for field_dict in clean_custom_field_list]

def build_entry_audit_dict(entry):
    """Data buat audit log. Isi access note ga ikut, cuma tanda ada/nggak."""
    return {
        "title": entry.title,
        "category_id": entry.category_id,
        "url": entry.url,
        "address": entry.address,
        "port": entry.port,
        "username": entry.username,
        "has_access_note": entry.encrypted_access_note is not None,
        "description": entry.description,
        "visibility": entry.visibility,
        "custom_field_label_list": [field.field_label for field in entry.custom_field_list],
        "attachment_name_list": [attachment.original_filename for attachment in entry.attachment_list],
    }

def save_entry_change(user, entry, prepared_upload_list, action, old_data_dict=None):
    """Tulis lampiran + catat audit + commit. Kalau gagal, file yg udah ketulis dihapus lagi."""
    written_path_list = []
    try:
        # flush dulu biar entry.id keisi
        db.session.flush()
        written_path_list = store_prepared_attachment_list(entry, user, prepared_upload_list)
        log_audit(
            action, AUDIT_ENTITY_TYPE, entity_id=entry.id,
            old_data_dict=old_data_dict, new_data_dict=build_entry_audit_dict(entry), user=user,
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        remove_file_path_list(written_path_list)
        raise

def create_access_entry(user, data_dict, custom_field_pair_list=None, upload_file_list=None):
    """Bikin data link baru (+ lampiran kalau ada)."""
    clean_dict, clean_custom_field_list, prepared_upload_list = prepare_entry_data(
        user, data_dict, custom_field_pair_list, upload_file_list,
    )

    entry = AccessEntry(user_id=user.id)
    apply_entry_data(entry, clean_dict, clean_custom_field_list)
    db.session.add(entry)
    save_entry_change(user, entry, prepared_upload_list, AUDIT_ACTION_CREATE)
    return entry

def update_access_entry(user, entry, data_dict, custom_field_pair_list=None,
                        upload_file_list=None, delete_attachment_id_list=None):
    """Ubah data link, bisa sekalian nambah & hapus lampiran."""
    if not can_edit_entry(user, entry):
        raise PermissionDeniedError("Kamu tidak punya akses mengubah data ini")

    # lampiran yg mau dihapus (cuma yg emang punya entry ini)
    delete_attachment_list = pick_entry_attachment_list(entry, delete_attachment_id_list)
    existing_attachment_count = len(entry.attachment_list) - len(delete_attachment_list)

    clean_dict, clean_custom_field_list, prepared_upload_list = prepare_entry_data(
        user, data_dict, custom_field_pair_list, upload_file_list,
        existing_attachment_count=existing_attachment_count, exclude_entry_id=entry.id,
        current_category_id=entry.category_id,
    )
    # visibilitas cuma boleh diganti pemiliknya
    if not is_entry_owner(user, entry):
        clean_dict["visibility"] = entry.visibility

    old_data_dict = build_entry_audit_dict(entry)
    apply_entry_data(entry, clean_dict, clean_custom_field_list)

    removed_filename_list = [attachment.stored_filename for attachment in delete_attachment_list]
    for attachment in delete_attachment_list:
        entry.attachment_list.remove(attachment)

    save_entry_change(user, entry, prepared_upload_list, AUDIT_ACTION_UPDATE, old_data_dict)
    # file lama baru dihapus setelah DB aman
    remove_stored_file_list(removed_filename_list)
    return entry

def delete_access_entry(user, entry):
    """Hapus data link + field tambahan + lampiran (DB & file)."""
    if not can_edit_entry(user, entry):
        raise PermissionDeniedError("Kamu tidak punya akses menghapus data ini")

    old_data_dict = build_entry_audit_dict(entry)
    stored_filename_list = [attachment.stored_filename for attachment in entry.attachment_list]
    entry_id = entry.id

    db.session.delete(entry)
    log_audit(AUDIT_ACTION_DELETE, AUDIT_ENTITY_TYPE, entity_id=entry_id, old_data_dict=old_data_dict, user=user)
    db.session.commit()
    remove_stored_file_list(stored_filename_list)

# AMBIL DATA
def get_visible_entry(user, entry_id):
    """Satu data kalau boleh diliat, None kalau nggak (dua-duanya jadi 404)."""
    return db.session.execute(
        db.select(AccessEntry)
        .options(
            joinedload(AccessEntry.category),
            joinedload(AccessEntry.owner),
            selectinload(AccessEntry.custom_field_list),
            selectinload(AccessEntry.attachment_list),
        )
        .where(AccessEntry.id == entry_id, build_visible_entry_filter(user))
    ).scalar_one_or_none()

def build_visible_entry_query(user, keyword=None, category_id=None, visibility=None, is_include_sub=True):
    """Query data yg boleh diliat user + filter (dipake tabel Home & export Excel biar hasilnya sama persis)."""
    query = (
        db.select(AccessEntry)
        .options(
            joinedload(AccessEntry.category),
            joinedload(AccessEntry.owner),
            selectinload(AccessEntry.attachment_list),
        )
        .where(build_visible_entry_filter(user))
    )
    clean_keyword = sanitize_text(keyword, max_length=MAX_SEARCH_KEYWORD_LENGTH)
    if clean_keyword:
        search_column_list = [AccessEntry.title, AccessEntry.url, AccessEntry.address, AccessEntry.description]
        query = query.where(build_keyword_filter(search_column_list, clean_keyword))
    if category_id:
        category = get_category(category_id)
        category_id_list = list_descendant_id(category) if category is not None and is_include_sub else [category_id]
        query = query.where(AccessEntry.category_id.in_(category_id_list))
    if visibility in VISIBILITY_LIST:
        query = query.where(AccessEntry.visibility == visibility)
    return query.order_by(AccessEntry.updated_at.desc(), AccessEntry.id.desc())

def search_visible_entries(user, keyword=None, category_id=None, visibility=None, page=1, per_page=DASHBOARD_PER_PAGE,
                           is_include_sub=True):
    """Cari data yg boleh diliat user, hasilnya per halaman. Filter kategori ikut ngambil isi sub-nya."""
    query = build_visible_entry_query(user, keyword, category_id, visibility, is_include_sub)
    return db.paginate(query, page=page, per_page=per_page, error_out=False)

def list_visible_entries_for_export(user, keyword=None, category_id=None, visibility=None, max_count=EXPORT_MAX_ROW_COUNT):
    """Semua data hasil filter buat export (dibatesin biar server ga berat). Return (entry_list, is_truncated)."""
    query = build_visible_entry_query(user, keyword, category_id, visibility).limit(max_count + 1)
    entry_list = db.session.execute(query).unique().scalars().all()
    return entry_list[:max_count], len(entry_list) > max_count

def count_visible_entry_summary(user):
    """Jumlah data per visibilitas dalam 1 query."""
    row_list = db.session.execute(
        db.select(AccessEntry.visibility, db.func.count(AccessEntry.id))
        .where(build_visible_entry_filter(user))
        .group_by(AccessEntry.visibility)
    ).all()
    count_by_visibility_dict = {visibility: count for visibility, count in row_list}
    return {
        "total": sum(count_by_visibility_dict.values()),
        "public": count_by_visibility_dict.get(VISIBILITY_PUBLIC, 0),
        "private": count_by_visibility_dict.get(VISIBILITY_PRIVATE, 0),
    }

def read_access_note(entry):
    """Buka access note. Return (isi, is_error)."""
    try:
        return decrypt_credential(entry.encrypted_access_note), False
    except InvalidCredentialError:
        return None, True