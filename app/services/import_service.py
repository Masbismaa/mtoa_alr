"""Import link dari Excel: download template, upload, cek SEMUA baris dulu, baru simpen semua (atau ga sama sekali).

Tiap baris dicek pake aturan yg sama persis kayak form Add Link (prepare_entry_data); duplikat ke database dicek
sekaligus semua baris (find_duplicate_entry_dict, aturannya sama kayak find_duplicate_entry).
Duplikat antar baris di file yg sama dicek di sini (belum ada di database). Link hasil import milik yg upload.
Opsi "Create categories": jalur kategori yg belum ada dibikin jadi kategori pribadi user di transaksi yg sama.
"""
import io
from collections import namedtuple

from openpyxl import load_workbook

from app.extensions import db
from app.models import AccessEntry, Category
from app.security.access_policy import is_admin
from app.security.file_validator import detect_content_type
from app.services.access_entry_service import (
    AUDIT_ENTITY_TYPE,
    apply_entry_data,
    get_category_rule,
    build_entry_audit_dict,
    find_duplicate_entry_dict,
    prepare_entry_data,
)
from app.services.audit_service import log_audit
from app.services.category_service import (
    AUDIT_CATEGORY,
    build_category_audit_dict,
    build_category_label,
    clear_request_category_cache,
    list_usable_category,
    validate_category_data,
)
from app.utils.constants import (
    ATTACHMENT_MAX_SIZE_BYTES,
    AUDIT_ACTION_CREATE,
    AUDIT_ACTION_IMPORT,
    CATEGORY_PATH_SEPARATOR,
    CATEGORY_SPECIFIC_FIELD_LIST,
    CREDENTIAL_FIELD_LIST,
    IMPORT_MAX_ROW_COUNT,
    MAX_CATEGORY_DEPTH,
    MAX_CATEGORY_NAME_LENGTH,
    VISIBILITY_PRIVATE,
    VISIBILITY_PUBLIC,
)
from app.utils.exceptions import ValidationError, build_error

# kolom template. header dicocokin tanpa beda huruf besar/kecil & tanda * (penanda wajib di template).
# width/guide/example cuma buat tampilan template (import_template_service.py)
ImportColumn = namedtuple("ImportColumn", ["header", "key", "is_required", "width", "guide", "example"])
IMPORT_COLUMN_LIST = [
    ImportColumn("Title", "title", True, 30, "Name of the link (max 150 characters).", "HR Portal"),
    ImportColumn("Category", "category", True, 26, "Pick from the dropdown (the Categories sheet shows which fields each one uses), "
                 "or type a new path and tick \"Create categories that don't exist yet\" when importing.", "Web > SAP"),
    ImportColumn("URL", "url", False, 36, "Starts with http:// or https://. Required for Web.", "https://hr.spindo.com"),
    ImportColumn("Address", "address", False, 20, "IP address or host name. Required for Network.", "10.0.0.1"),
    ImportColumn("Port", "port", False, 9, "Number from 1 to 65535.", "22"),
    ImportColumn("Username", "username", False, 20, "Login username (not used by General).", "hr.admin"),
    ImportColumn("Access Note", "access_note", False, 26, "Access hint, not a password (not used by General).", "Login via SSO"),
    ImportColumn("Description", "description", False, 40, "Short note about the link.", "Payroll & leave portal"),
    ImportColumn("Visibility", "visibility", False, 12, "Private (only you) or Public (all users, read-only). Empty = Private.", "Private"),
]
REQUIRED_HEADER_LIST = [column.key for column in IMPORT_COLUMN_LIST if column.is_required]
# kop template makan beberapa baris di atas header, jadi header dicari di sekian baris pertama
HEADER_SEARCH_ROW_COUNT = 10
VISIBILITY_BY_TEXT_DICT = {"": VISIBILITY_PRIVATE, "private": VISIBILITY_PRIVATE, "public": VISIBILITY_PUBLIC}
# error yg ditampilin dibatesin biar halaman ga kepanjangan; sisanya cukup disebut jumlahnya
MAX_SHOWN_ERROR_COUNT = 50
CREATE_CATEGORY_HINT = 'tick "Create categories that don\'t exist yet" to create it'


def list_import_column(user):
    """Kolom template buat user ini. Non-admin selalu Private, jadi kolom Visibility cuma ada di template admin."""
    return IMPORT_COLUMN_LIST if is_admin(user) else [column for column in IMPORT_COLUMN_LIST if column.key != "visibility"]


def split_category_path(text):
    """'Web > SAP', 'Web › SAP ' -> ['Web', 'SAP'] (huruf asli, bagian kosong dibuang)."""
    return [part.strip() for part in text.replace("›", ">").split(">") if part.strip()]


def normalize_category_path(text):
    """'Web > SAP', 'web › sap ' -> 'web › sap' (huruf kecil, pemisah disamain) buat dicocokin ke jalur kategori."""
    return CATEGORY_PATH_SEPARATOR.join(split_category_path(text)).lower()


def build_category_dict(user):
    """Jalur kategori aktif milik user (huruf kecil) -> Category, misal 'web › sap' -> SAP."""
    return {normalize_category_path(build_category_label(category)): category for category in list_usable_category(user)}


def normalize_header(value):
    """Judul kolom: 'Title *' / ' title' -> 'title'."""
    return cell_text(value).rstrip("*").strip().lower()


def cell_text(value):
    """Isi sel jadi teks: 22.0 -> '22', kosong -> ''."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def read_import_row_list(file_storage):
    """Baca file upload. Return [(nomor baris Excel, {key: teks})]. File salah format -> ValidationError."""
    filename = file_storage.filename or ""
    content_bytes = file_storage.stream.read(ATTACHMENT_MAX_SIZE_BYTES + 1)
    if not filename.lower().endswith(".xlsx"):
        raise ValidationError([build_error("import_file", "Upload the .xlsx file made from the template")])
    if len(content_bytes) > ATTACHMENT_MAX_SIZE_BYTES:
        raise ValidationError([build_error("import_file", f"The file is larger than {ATTACHMENT_MAX_SIZE_BYTES // 1048576}MB")])
    try:
        # cek isi beneran xlsx (bukan file lain yg diganti namanya), tanpa makro, ga bisa jadi zip bomb
        detect_content_type(filename, content_bytes)
    except ValueError as error:
        raise ValidationError([build_error("import_file", f"File rejected: {error}")]) from None
    key_by_header_dict = {column.header.lower(): column.key for column in IMPORT_COLUMN_LIST}
    try:
        sheet = load_workbook(io.BytesIO(content_bytes), read_only=True, data_only=True).worksheets[0]
        row_iter = enumerate(sheet.iter_rows(values_only=True), start=1)
        column_key_list = first_key_list = None
        for row_number, raw_row in row_iter:
            key_list = [key_by_header_dict.get(normalize_header(value)) for value in raw_row]
            if first_key_list is None and any(cell_text(value) for value in raw_row):
                first_key_list = key_list
            if all(key in key_list for key in REQUIRED_HEADER_LIST):
                column_key_list = key_list
                break
            if row_number >= HEADER_SEARCH_ROW_COUNT:
                break
        if column_key_list is None:
            found_key_list = first_key_list or []
            missing_header_list = [column.header for column in IMPORT_COLUMN_LIST
                                   if column.is_required and column.key not in found_key_list]
            raise ValidationError([build_error("import_file", f"Missing column(s): {', '.join(missing_header_list)}. Use the template.")])

        row_list = []
        for row_number, raw_row in row_iter:
            row_dict = {key: cell_text(value) for key, value in zip(column_key_list, raw_row) if key}
            if not any(row_dict.values()):
                continue
            if len(row_list) >= IMPORT_MAX_ROW_COUNT:
                raise ValidationError([build_error("import_file", f"Up to {IMPORT_MAX_ROW_COUNT} links per import; split the file.")])
            row_list.append((row_number, row_dict))
    except (ValueError, KeyError, OSError, IndexError):
        raise ValidationError([build_error("import_file", "The file can't be read as an Excel template")]) from None
    if not row_list:
        raise ValidationError([build_error("import_file", "The file has no links to import")])
    return row_list


def create_import_category(user, name, parent, depth):
    """Satu kategori pribadi baru (aturan sama kayak menu Categories), di-flush biar id-nya kepake baris link.
    Belum di-commit: kalau ada baris salah, import_entries rollback dan kategorinya ikut batal."""
    if depth > MAX_CATEGORY_DEPTH:
        raise ValidationError([build_error("category", f"Categories can be at most {MAX_CATEGORY_DEPTH} levels deep")])
    # dicek sebelum validate_category_data: sanitize_text di sana motong nama kepanjangan diem-diem
    if len(name) > MAX_CATEGORY_NAME_LENGTH:
        raise ValidationError([build_error("category", f"Category names can be at most {MAX_CATEGORY_NAME_LENGTH} characters")])
    clean_dict = validate_category_data({"name": name}, parent=parent, owner_id=user.id)
    category = Category(**clean_dict, parent_id=parent.id if parent else None, user_id=user.id, is_active=True)
    db.session.add(category)
    db.session.flush()
    log_audit(AUDIT_ACTION_CREATE, AUDIT_CATEGORY, entity_id=category.id, new_data_dict=build_category_audit_dict(category), user=user)
    return category


def create_missing_category(user, row_list, category_dict):
    """Bikin tiap tingkat jalur kategori yg belum ada (misal 'Proyek X > Server' -> Proyek X, lalu Server di bawahnya),
    category_dict ikut diisi. Return (label kategori baru, {nomor baris: [error]})."""
    new_label_list, error_by_row_dict, failed_dict = [], {}, {}
    for row_number, row_dict in row_list:
        part_list = split_category_path(row_dict.get("category", ""))
        parent = None
        for depth in range(1, len(part_list) + 1):
            path_text = CATEGORY_PATH_SEPARATOR.join(part_list[:depth])
            key = path_text.lower()
            if key in category_dict:
                parent = category_dict[key]
                continue
            if key not in failed_dict:
                try:
                    category = create_import_category(user, part_list[depth - 1], parent, depth)
                except ValidationError as error:
                    failed_dict[key] = f'Can\'t create category "{path_text}": {error.error_list[0]["message"]}'
                else:
                    category_dict[key] = parent = category
                    new_label_list.append(path_text)
                    continue
            error_by_row_dict[row_number] = [failed_dict[key]]
            break
    if new_label_list:
        clear_request_category_cache()
    return new_label_list, error_by_row_dict


def build_row_data(row_dict, category_dict, is_create_category=False):
    """Isi satu baris jadi data form link + daftar error yg ketauan sebelum dicek aturan link."""
    error_list = []
    category = category_dict.get(normalize_category_path(row_dict.get("category", "")))
    if category is None:
        hint = "" if is_create_category else f", or {CREATE_CATEGORY_HINT}"
        error_list.append(f'Unknown or inactive category "{row_dict.get("category", "")}" (see the Categories sheet{hint})')
    else:
        error_list.extend(find_unused_column_error_list(row_dict, category))
    visibility = VISIBILITY_BY_TEXT_DICT.get(row_dict.get("visibility", "").lower())
    if visibility is None:
        error_list.append("Visibility must be Public or Private")
    data_dict = {column.key: row_dict.get(column.key, "") for column in IMPORT_COLUMN_LIST
                 if column.key not in ("category", "visibility")}
    data_dict.update(category_id=category.id if category else None, visibility=visibility)
    return data_dict, error_list


def find_unused_column_error_list(row_dict, category):
    """Kolom keisi tapi ga dipake kategori ini (misal Access Note di General). Aturan link bakal ngebuang isinya
    diem-diem, jadi di import ditolak biar password/URL yg diisi user ga ilang tanpa ketauan."""
    rule = get_category_rule(category)
    used_key_set = set(rule["field_list"]) | (set(CREDENTIAL_FIELD_LIST) if rule["has_credential_field"] else set())
    return [
        f"{column.header} is not used by category {build_category_label(category)}"
        for column in IMPORT_COLUMN_LIST
        if column.key in CATEGORY_SPECIFIC_FIELD_LIST + CREDENTIAL_FIELD_LIST
        and column.key not in used_key_set and row_dict.get(column.key)
    ]


def find_duplicate_in_file(clean_dict, seen_dict, row_number):
    """Cek URL / Address+Port udah dipake baris lain di file ini. Return pesan error atau None."""
    key_dict = {}
    if clean_dict.get("url"):
        key_dict["URL"] = ("url", clean_dict["url"])
    if clean_dict.get("address"):
        key_dict["Address/Port"] = ("address", clean_dict["address"], clean_dict.get("port"))
    for label, key in key_dict.items():
        if key in seen_dict:
            return f"Same {label} as row {seen_dict[key]}"
    for key in key_dict.values():
        seen_dict[key] = row_number
    return None


def import_entries(user, file_storage, is_create_category=False):
    """Import semua baris. Ada 1 baris salah -> ga ada yg disimpen (kategori baru juga), ValidationError isinya
    error per baris. Semua bener -> disimpen dalam 1 transaksi + dicatat (per link & 1 catatan import).
    Return (jumlah link, label kategori baru)."""
    row_list = read_import_row_list(file_storage)
    if not is_admin(user):
        # non-admin selalu Private: kolom Visibility (file template admin / lama) diabaikan
        for _, row_dict in row_list:
            row_dict.pop("visibility", None)
    category_dict = build_category_dict(user)
    new_category_label_list, error_by_row_dict = [], {}
    if is_create_category:
        new_category_label_list, error_by_row_dict = create_missing_category(user, row_list, category_dict)
    # (nomor baris, clean_dict, field tambahan) yg lolos validasi per baris
    prepared_list = []
    seen_dict = {}
    for row_number, row_dict in row_list:
        if row_number in error_by_row_dict:
            continue
        data_dict, row_error_list = build_row_data(row_dict, category_dict, is_create_category)
        if not row_error_list:
            try:
                # duplikat ke database dicek sekaligus di bawah (1 query, bukan 1 query per baris)
                clean_dict, clean_custom_field_list, _ = prepare_entry_data(user, data_dict, [], check_duplicate=False)
            except ValidationError as error:
                row_error_list = [error_dict["message"] for error_dict in error.error_list]
            else:
                duplicate_text = find_duplicate_in_file(clean_dict, seen_dict, row_number)
                if duplicate_text:
                    row_error_list = [duplicate_text]
                else:
                    prepared_list.append((row_number, clean_dict, clean_custom_field_list))
        if row_error_list:
            error_by_row_dict[row_number] = row_error_list
    duplicate_dict = find_duplicate_entry_dict(user, [clean_dict for _, clean_dict, _ in prepared_list])
    for index, message in duplicate_dict.items():
        error_by_row_dict[prepared_list[index][0]] = [message]

    if error_by_row_dict:
        # kategori yg udah di-flush ikut dibatalin
        db.session.rollback()
        clear_request_category_cache()
        error_text_list = [f"Row {row_number}: {message}"
                           for row_number in sorted(error_by_row_dict) for message in error_by_row_dict[row_number]]
        shown_list = error_text_list[:MAX_SHOWN_ERROR_COUNT]
        if len(error_text_list) > MAX_SHOWN_ERROR_COUNT:
            shown_list.append(f"...and {len(error_text_list) - MAX_SHOWN_ERROR_COUNT} more errors")
        raise ValidationError([build_error("import_file", text) for text in shown_list])

    try:
        entry_list = []
        for _, clean_dict, clean_custom_field_list in prepared_list:
            # lampiran diisi kosong dari awal: audit di bawah baca daftar ini, biar ga 1 SELECT per link
            entry = AccessEntry(user_id=user.id, attachment_list=[])
            apply_entry_data(entry, clean_dict, clean_custom_field_list)
            entry_list.append(entry)
        db.session.add_all(entry_list)
        # sekali flush buat semua link (id-nya kepake di audit), bukan flush per baris
        db.session.flush()
        for entry in entry_list:
            log_audit(AUDIT_ACTION_CREATE, AUDIT_ENTITY_TYPE, entity_id=entry.id, new_data_dict=build_entry_audit_dict(entry), user=user)
        import_log_dict = {"row_count": len(entry_list), "filename": (file_storage.filename or "")[:255]}
        if new_category_label_list:
            import_log_dict["new_category_list"] = new_category_label_list
        log_audit(AUDIT_ACTION_IMPORT, AUDIT_ENTITY_TYPE, user=user, new_data_dict=import_log_dict)
        db.session.commit()
    except Exception:
        db.session.rollback()
        clear_request_category_cache()
        raise
    return len(entry_list), new_category_label_list
