"""Logika CRUD Access Entry. Route tinggal manggil fungsi di sini."""
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.models import AccessEntry, AccessEntryField, Category
from app.security.access_policy import build_visible_entry_filter, can_edit_entry, is_entry_owner
from app.security.encryption_service import decrypt_credential, encrypt_credential
from app.services.audit_service import log_audit
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
)
from app.utils.exceptions import InvalidCredentialError, PermissionDeniedError, ValidationError
from app.utils.sanitizer import get_plain_text, sanitize_rich_text, sanitize_text
from app.utils.url_helper import normalize_address, normalize_url, parse_port

AUDIT_ENTITY_TYPE = "access_entries"

# kolom yg langsung disalin dari data bersih ke model
ENTRY_COLUMN_FIELD_LIST = ["category_id", "title", "url", "address", "port", "username", "description", "visibility"]

# fungsi validasi buat tiap field khusus kategori
FIELD_NORMALIZER_DICT = {"url": normalize_url, "address": normalize_address, "port": parse_port}


def build_error(field, message):
    """Bikin satu item error (formatnya sama kayak error_list di response)."""
    return {"field": field, "message": message}


# KATEGORI
def get_category_rule(category_name):
    """Aturan field untuk kategori tertentu."""
    return CATEGORY_FIELD_RULE_DICT.get(category_name, DEFAULT_CATEGORY_FIELD_RULE)


def get_active_category_list():
    """Semua kategori aktif, urut sesuai id (Web, Application, Network, General)."""
    return db.session.execute(db.select(Category).filter_by(is_active=True).order_by(Category.id)).scalars().all()


def get_category_from_id(raw_category_id):
    """Ambil kategori aktif dari id. None kalau ga ada / nonaktif / id ngaco."""
    try:
        category_id = int(raw_category_id)
    except (TypeError, ValueError):
        return None
    category = db.session.get(Category, category_id)
    if category is None or not category.is_active:
        return None
    return category


def build_category_option_list(category_list):
    """Data dropdown kategori + aturan field-nya (dipake JS buat nampilin/nyembunyiin field)."""
    option_list = []
    for category in category_list:
        rule = get_category_rule(category.name)
        option_list.append({
            "id": category.id,
            "name": category.name,
            "field_list": ",".join(rule["field_list"]),
            "required_field_list": ",".join(rule["required_field_list"]),
            "has_custom_field": "true" if rule["has_custom_field"] else "false",
        })
    return option_list


# VALIDASI

def validate_entry_data(data_dict):
    """Cek & bersihin data utama. Return (clean_dict, category, error_list)."""
    category = get_category_from_id(data_dict.get("category_id"))
    if category is None:
        return {}, None, [build_error("category_id", "Kategori tidak valid")]

    rule = get_category_rule(category.name)
    error_list = []
    clean_dict = {"category_id": category.id}

    # judul
    clean_dict["title"] = sanitize_text(data_dict.get("title"), max_length=MAX_TITLE_LENGTH)
    if not clean_dict["title"]:
        error_list.append(build_error("title", "Judul wajib diisi"))

    # field khusus kategori: yg ga dipake kategori ini otomatis dikosongin
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

    # field umum
    clean_dict["username"] = sanitize_text(data_dict.get("username"), max_length=MAX_USERNAME_LENGTH) or None

    raw_access_note = data_dict.get("access_note") or ""
    if len(raw_access_note) > MAX_ACCESS_NOTE_LENGTH:
        error_list.append(build_error("access_note", f"Access note maksimal {MAX_ACCESS_NOTE_LENGTH} karakter"))
    # sengaja ga di-sanitize biar karakter password ga berubah (nanti dienkripsi)
    clean_dict["access_note"] = raw_access_note if raw_access_note.strip() else None

    clean_dict["description"] = sanitize_text(data_dict.get("description")) or None

    visibility = data_dict.get("visibility")
    if visibility not in VISIBILITY_LIST:
        error_list.append(build_error("visibility", "Pilih Public atau Private"))
    clean_dict["visibility"] = visibility

    return clean_dict, category, error_list


def validate_custom_field_list(category, custom_field_pair_list):
    """Cek field tambahan (cuma buat kategori yg punya 'Add field'). Return (clean_list, error_list)."""
    rule = get_category_rule(category.name)
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
    """Cari data yg URL / Address+Port-nya sama.

    Cuma dibandingin sama data yg boleh dilihat user (punya sendiri + Public),
    biar data Private orang lain ga bocor lewat pesan 'duplikat'.

    Return (nama_field, entry) atau (None, None).
    """
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

def prepare_entry_data(user, data_dict, custom_field_pair_list, exclude_entry_id=None):
    """Gabungan semua validasi (dipake create & update). Lempar ValidationError kalau ada yg salah."""
    clean_dict, category, error_list = validate_entry_data(data_dict)

    clean_custom_field_list = []
    if category is not None:
        clean_custom_field_list, custom_error_list = validate_custom_field_list(category, custom_field_pair_list)
        error_list.extend(custom_error_list)

    # cek duplikat cuma kalau data lain udah bener (hemat query)
    if not error_list:
        duplicate_field, duplicate_entry = find_duplicate_entry(user, clean_dict, exclude_entry_id)
        if duplicate_entry is not None:
            error_list.append(build_error(duplicate_field, f'Sudah terdaftar di data "{duplicate_entry.title}"'))

    if error_list:
        raise ValidationError(error_list)
    return clean_dict, clean_custom_field_list

# SIMPAN
def apply_entry_data(entry, clean_dict, clean_custom_field_list):
    """Salin data bersih ke objek entry (access note dienkripsi, field tambahan diganti semua)."""
    for field_name in ENTRY_COLUMN_FIELD_LIST:
        setattr(entry, field_name, clean_dict[field_name])
    entry.encrypted_access_note = encrypt_credential(clean_dict["access_note"])
    # ganti list = field lama otomatis kehapus (delete-orphan)
    entry.custom_field_list = [AccessEntryField(**field_dict) for field_dict in clean_custom_field_list]

def build_entry_audit_dict(entry):
    """Data yg dicatat ke audit log. Isi access note ga ikut, cuma tanda ada/nggak."""
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
    }

def create_access_entry(user, data_dict, custom_field_pair_list=None):
    """Bikin data link baru milik user."""
    clean_dict, clean_custom_field_list = prepare_entry_data(user, data_dict, custom_field_pair_list)

    entry = AccessEntry(user_id=user.id)
    apply_entry_data(entry, clean_dict, clean_custom_field_list)
    db.session.add(entry)
    # flush biar entry.id udah keisi buat audit
    db.session.flush()

    log_audit(AUDIT_ACTION_CREATE, AUDIT_ENTITY_TYPE, entity_id=entry.id, new_data_dict=build_entry_audit_dict(entry), user=user)
    db.session.commit()
    return entry

def update_access_entry(user, entry, data_dict, custom_field_pair_list=None):
    """Ubah data link. Dicek dulu haknya (lapis kedua setelah route)."""
    if not can_edit_entry(user, entry):
        raise PermissionDeniedError("Kamu tidak punya akses mengubah data ini")

    clean_dict, clean_custom_field_list = prepare_entry_data(
        user, data_dict, custom_field_pair_list, exclude_entry_id=entry.id,
    )
    # visibilitas cuma boleh diganti pemiliknya
    if not is_entry_owner(user, entry):
        clean_dict["visibility"] = entry.visibility

    old_data_dict = build_entry_audit_dict(entry)
    apply_entry_data(entry, clean_dict, clean_custom_field_list)
    new_data_dict = build_entry_audit_dict(entry)

    log_audit(
        AUDIT_ACTION_UPDATE, AUDIT_ENTITY_TYPE, entity_id=entry.id,
        old_data_dict=old_data_dict, new_data_dict=new_data_dict, user=user,
    )
    db.session.commit()
    return entry

def delete_access_entry(user, entry):
    """Hapus data link (field tambahan ikut kehapus)."""
    if not can_edit_entry(user, entry):
        raise PermissionDeniedError("Kamu tidak punya akses menghapus data ini")

    old_data_dict = build_entry_audit_dict(entry)
    entry_id = entry.id
    db.session.delete(entry)
    log_audit(AUDIT_ACTION_DELETE, AUDIT_ENTITY_TYPE, entity_id=entry_id, old_data_dict=old_data_dict, user=user)
    db.session.commit()

# AMBIL DATA
def get_visible_entry(user, entry_id):
    """Ambil satu data kalau user boleh liat. None kalau ga ada / ga boleh (dua-duanya jadi 404)."""
    return db.session.execute(
        db.select(AccessEntry)
        .options(
            joinedload(AccessEntry.category),
            joinedload(AccessEntry.owner),
            selectinload(AccessEntry.custom_field_list),
        )
        .where(AccessEntry.id == entry_id, build_visible_entry_filter(user))
    ).scalar_one_or_none()

def list_visible_entries(user, limit=20):
    """Data terbaru yg boleh dilihat user. Kategori & pembuat diambil sekalian (anti query berulang)."""
    return db.session.execute(
        db.select(AccessEntry)
        .options(joinedload(AccessEntry.category), joinedload(AccessEntry.owner))
        .where(build_visible_entry_filter(user))
        .order_by(AccessEntry.updated_at.desc(), AccessEntry.id.desc())
        .limit(limit)
    ).scalars().all()

def count_visible_entry_summary(user):
    """Jumlah data per visibilitas dalam SATU query: total, public, private (punya sendiri)."""
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
    """Buka access note. Return (isi, is_error). is_error True kalau key enkripsi beda/data rusak."""
    try:
        return decrypt_credential(entry.encrypted_access_note), False
    except InvalidCredentialError:
        return None, True