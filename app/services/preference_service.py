"""Ambil & ubah preferensi tampilan user."""
import re
from urllib.parse import parse_qsl, urlencode

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import SelectionVariant, User, UserPreference
from app.schemas.table_schema import TABLE_COLUMN_DICT
from app.services.audit_service import log_audit
from app.utils.constants import (
    ACCENT_KEY_BY_HEX_DICT,
    AUDIT_ACTION_UPDATE,
    DEFAULT_ACCENT_KEY,
    DEFAULT_ACCENT_COLOR,
    DEFAULT_FONT_FAMILY,
    THEME_MODE_LIGHT,
    FONT_FAMILY_KEY_LIST,
    TABLE_COLUMN_MAX_WIDTH,
    TABLE_COLUMN_MIN_WIDTH,
    THEME_MODE_LIST,
    MAX_VARIANT_NAME_LENGTH,
    MAX_VARIANT_QUERY_LENGTH,
    SELECTION_VARIANT_MAX_COUNT,
)
from app.utils.data_table import build_default_layout
from app.utils.exceptions import ValidationError, build_error
from app.utils.sanitizer import sanitize_text
from app.utils.url_helper import get_safe_back_url

# cuma field ini yg boleh diubah lewat API, sisanya ditolak
PREFERENCE_FIELD_LIST = ["theme_mode", "accent_color", "is_compact_view", "font_family"]

def get_or_create_preference(user, for_write=False):
    """Render memakai default tanpa menulis DB; perubahan disimpan oleh transaksi pemanggil."""
    if for_write:
        db.session.execute(db.select(User.id).where(User.id == user.id).with_for_update()).scalar_one()
        preference = db.session.execute(db.select(UserPreference).where(UserPreference.user_id == user.id)
                                        .execution_options(populate_existing=True)).scalar_one_or_none()
    else:
        preference = user.preference
    if preference is None:
        preference = UserPreference(theme_mode=THEME_MODE_LIGHT, accent_color=DEFAULT_ACCENT_COLOR,
                                    font_family=DEFAULT_FONT_FAMILY, is_compact_view=False, table_layout={})
        if for_write:
            user.preference = preference
            db.session.flush()
    return preference

def build_preference_dict(preference):
    """Preferensi dalam bentuk dict (dipake buat audit & response)."""
    return {field: getattr(preference, field) for field in PREFERENCE_FIELD_LIST}

def build_ui_preference_dict(preference):
    """Sama kayak build_preference_dict + accent_key buat CSS (data-accent)."""
    ui_preference_dict = build_preference_dict(preference)
    ui_preference_dict["accent_key"] = ACCENT_KEY_BY_HEX_DICT.get(preference.accent_color, DEFAULT_ACCENT_KEY)
    return ui_preference_dict

def validate_preference_data(data_dict):
    """Cek data dari user satu-satu. Return (clean_dict, error_list)."""
    clean_dict = {}
    error_list = []

    if not data_dict:
        return clean_dict, [{"field": None, "message": "No preferences were changed"}]

    for key, value in data_dict.items():
        # field asing (misal 'role') langsung ditolak
        if key not in PREFERENCE_FIELD_LIST:
            error_list.append({"field": str(key)[:50], "message": "Unknown field"})
        elif key == "theme_mode" and value not in THEME_MODE_LIST:
            error_list.append({"field": key, "message": "Display mode must be light or dark"})
        elif key == "accent_color" and (not isinstance(value, str) or value.lower() not in ACCENT_KEY_BY_HEX_DICT):
            error_list.append({"field": key, "message": "Accent color not available"})
        elif key == "is_compact_view" and not isinstance(value, bool):
            error_list.append({"field": key, "message": "Density must be true or false"})
        elif key == "font_family" and value not in FONT_FAMILY_KEY_LIST:
            error_list.append({"field": key, "message": "Font not available"})
        else:
            # hex disimpen huruf kecil biar konsisten
            clean_dict[key] = value.lower() if key == "accent_color" else value

    return clean_dict, error_list

def update_preference(user, data_dict):
    """Ubah sebagian/semua preferensi. Lempar ValidationError kalau ada yg ga valid."""
    clean_dict, error_list = validate_preference_data(data_dict)
    if error_list:
        raise ValidationError(error_list)

    had_preference = user.preference is not None
    preference = get_or_create_preference(user, for_write=True)
    old_data_dict = build_preference_dict(preference)

    for key, value in clean_dict.items():
        setattr(preference, key, value)

    # cuma disimpen + dicatat kalau emang ada yg berubah
    new_data_dict = build_preference_dict(preference)
    if new_data_dict != old_data_dict:
        log_audit(
            AUDIT_ACTION_UPDATE, "user_preferences", entity_id=preference.id,
            old_data_dict=old_data_dict, new_data_dict=new_data_dict, user=user,
        )
        db.session.commit()
    elif not had_preference:
        db.session.commit()
    return preference

# LAYOUT TABEL ALA ALV (kolom disembunyiin + lebar kolom), disimpen per tabel
TABLE_LAYOUT_FIELD_LIST = ["table_key", "hidden_list", "width_dict", "client_id", "sequence"]
# urutan simpan terakhir per tab browser: {table_key: {client_id: sequence}} (maks 20 tab), di kolom JSON yg sama
TABLE_LAYOUT_SAVE_STATE_KEY = "_save_state"
# nomor urut terakhir diinget buat sekian tab terbaru per tabel (tab lama yg ga dipake lagi kebuang sendiri)
TABLE_LAYOUT_CLIENT_LIMIT = 20
CLIENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")

def get_table_layout(user, table_key):
    """Layout tabel yg disimpen user. Belum pernah ngatur -> layout bawaan (ga bikin baris preferensi baru)."""
    saved_layout_dict = (user.preference.table_layout or {}).get(table_key) if user.preference else None
    return saved_layout_dict or build_default_layout(table_key)

def is_valid_width(value):
    """Lebar kolom harus angka bulat dalam batas wajar (bool ditolak walaupun di Python termasuk int)."""
    return isinstance(value, int) and not isinstance(value, bool) and TABLE_COLUMN_MIN_WIDTH <= value <= TABLE_COLUMN_MAX_WIDTH

def clean_table_layout(data_dict):
    """Cek layout dari JS. Return (table_key, layout_dict), lempar ValidationError kalau ada yg ga valid."""
    error_list = [build_error(str(key)[:50], "Unknown field") for key in data_dict if key not in TABLE_LAYOUT_FIELD_LIST]
    table_key = data_dict.get("table_key")
    column_list = TABLE_COLUMN_DICT.get(table_key) if isinstance(table_key, str) else None
    if column_list is None:
        raise ValidationError(error_list + [build_error("table_key", "Unknown table")])
    hideable_key_list = [column.key for column in column_list if column.is_hideable]
    column_key_list = [column.key for column in column_list]
    hidden_list = data_dict.get("hidden_list", [])
    width_dict = data_dict.get("width_dict", {})
    if not isinstance(hidden_list, list) or any(key not in hideable_key_list for key in hidden_list):
        error_list.append(build_error("hidden_list", "Invalid hidden columns"))
    if not isinstance(width_dict, dict) or any(
        key not in column_key_list or not is_valid_width(value) for key, value in width_dict.items()
    ):
        error_list.append(build_error("width_dict", f"Column width must be {TABLE_COLUMN_MIN_WIDTH}-{TABLE_COLUMN_MAX_WIDTH} px"))
    save_order = read_layout_save_order(data_dict, error_list)
    if error_list:
        raise ValidationError(error_list)
    # urutannya ngikut daftar kolom & dobel dibuang biar data yg kesimpen rapi
    clean_hidden_list = [key for key in hideable_key_list if key in hidden_list]
    return table_key, {"hidden_list": clean_hidden_list, "width_dict": width_dict}, save_order

def read_layout_save_order(data_dict, error_list):
    """client_id (acak per tab browser) + sequence (naik terus tiap kirim). Opsional, tapi harus berpasangan.
    Dipake buat nolak kiriman lama yg telat nyampe (lihat update_table_layout)."""
    client_id, sequence = data_dict.get("client_id"), data_dict.get("sequence")
    if client_id is None and sequence is None:
        return None
    is_valid_client_id = isinstance(client_id, str) and CLIENT_ID_PATTERN.match(client_id)
    is_valid_sequence = isinstance(sequence, int) and not isinstance(sequence, bool) and 0 <= sequence < 2 ** 53
    if not (is_valid_client_id and is_valid_sequence):
        error_list.append(build_error("sequence", "Invalid layout save sequence"))
        return None
    return {"client_id": client_id, "sequence": sequence}

def update_table_layout(user, data_dict):
    """Simpen layout satu tabel. Ga dicatat di audit log: cuma tampilan pribadi & bisa berubah tiap kolom digeser.
    Return (layout yg berlaku sekarang, is_stale).

    is_stale True = kiriman ini lebih lama dari yg udah kesimpen dari tab yg sama (sequence <= yg terakhir tab itu),
    jadi DIABAIKAN. Kejadian kalau request lama telat nyampe, misal kalah duluan sama kiriman pas halaman ditutup.
    Nomor urut diinget PER TAB (urutan A-2, B-1, lalu A-1 telat -> A-1 tetep ditolak).
    Antar tab/perangkat (client_id beda) tetep "yg terakhir nyampe yg menang"."""
    table_key, layout_dict, save_order = clean_table_layout(data_dict)
    # baris user dikunci: kiriman barengan diproses satu-satu, jadi perbandingan sequence-nya aman
    preference = get_or_create_preference(user, for_write=True)
    table_layout = dict(preference.table_layout or {})
    save_state_dict = dict(table_layout.get(TABLE_LAYOUT_SAVE_STATE_KEY) or {})
    # {client_id: sequence terakhir}, urut dari tab yg paling lama ga ngirim
    sequence_dict = dict(save_state_dict.get(table_key) or {})
    if save_order and save_order["sequence"] <= sequence_dict.get(save_order["client_id"], -1):
        db.session.rollback()
        return table_layout.get(table_key) or build_default_layout(table_key), True
    table_layout[table_key] = layout_dict
    if save_order:
        sequence_dict.pop(save_order["client_id"], None)
        sequence_dict[save_order["client_id"]] = save_order["sequence"]
        save_state_dict[table_key] = dict(list(sequence_dict.items())[-TABLE_LAYOUT_CLIENT_LIMIT:])
        table_layout[TABLE_LAYOUT_SAVE_STATE_KEY] = save_state_dict
    # dict baru biar SQLAlchemy sadar kolom JSON-nya berubah
    preference.table_layout = table_layout
    db.session.commit()
    return layout_dict, False


# VARIANT KRITERIA PENCARIAN (Save as Variant / Get Variant ala Select Screen SAP)

def clean_variant_query(query_text):
    """Query string kriteria: nomor halaman dibuang (variant = kriterianya aja), isian kosong ga ikut."""
    pair_list = [(key, value) for key, value in parse_qsl((query_text or "").lstrip("?"), keep_blank_values=False)
                 if key != "page"]
    return urlencode(pair_list)


def list_selection_variant(user, screen_path):
    return db.session.execute(
        db.select(SelectionVariant).filter_by(user_id=user.id, screen_path=screen_path).order_by(SelectionVariant.name)
    ).scalars().all()


def save_selection_variant(user, screen_path, name, query_text):
    """Simpen kriteria pake nama. Nama sama di layar yg sama -> ditimpa. Return variant."""
    clean_path = get_safe_back_url(screen_path)
    clean_name = sanitize_text(name, max_length=MAX_VARIANT_NAME_LENGTH)
    clean_query = clean_variant_query(query_text)
    error_list = []
    if clean_path is None or "?" in clean_path:
        error_list.append(build_error("screen_path", "Invalid screen"))
    if not clean_name:
        error_list.append(build_error("name", "Variant name is required"))
    if len(clean_query) > MAX_VARIANT_QUERY_LENGTH:
        error_list.append(build_error("query_text", "The criteria are too long to save as a variant"))
    if error_list:
        raise ValidationError(error_list)
    variant = db.session.execute(
        db.select(SelectionVariant).filter_by(user_id=user.id, screen_path=clean_path, name=clean_name)
    ).scalar_one_or_none()
    if variant is None:
        if len(list_selection_variant(user, clean_path)) >= SELECTION_VARIANT_MAX_COUNT:
            raise ValidationError([build_error("name", f"Up to {SELECTION_VARIANT_MAX_COUNT} variants per screen; delete one first")])
        variant = SelectionVariant(user_id=user.id, screen_path=clean_path, name=clean_name)
        db.session.add(variant)
    variant.query_text = clean_query
    try:
        db.session.commit()
    except IntegrityError:
        # simpen nama yg sama barengan dari 2 tab: yg kalah ga perlu error, variant-nya udah ada
        db.session.rollback()
    return variant


def delete_selection_variant(user, variant_id):
    """Hapus variant punya sendiri. Return screen_path-nya (buat balik ke layar itu), None kalau ga ketemu."""
    variant = db.session.execute(
        db.select(SelectionVariant).filter_by(id=variant_id, user_id=user.id)
    ).scalar_one_or_none()
    if variant is None:
        return None
    screen_path = variant.screen_path
    db.session.delete(variant)
    db.session.commit()
    return screen_path
