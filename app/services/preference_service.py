"""Ambil & ubah preferensi tampilan user."""
from app.extensions import db
from app.models import User, UserPreference
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
)
from app.utils.data_table import build_default_layout
from app.utils.exceptions import ValidationError, build_error

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
        return clean_dict, [{"field": None, "message": "Tidak ada preferensi yang diubah"}]

    for key, value in data_dict.items():
        # field asing (misal 'role') langsung ditolak
        if key not in PREFERENCE_FIELD_LIST:
            error_list.append({"field": str(key)[:50], "message": "Field tidak dikenal"})
        elif key == "theme_mode" and value not in THEME_MODE_LIST:
            error_list.append({"field": key, "message": "Mode tampilan harus light atau dark"})
        elif key == "accent_color" and (not isinstance(value, str) or value.lower() not in ACCENT_KEY_BY_HEX_DICT):
            error_list.append({"field": key, "message": "Warna aksen tidak tersedia"})
        elif key == "is_compact_view" and not isinstance(value, bool):
            error_list.append({"field": key, "message": "Kerapatan harus true atau false"})
        elif key == "font_family" and value not in FONT_FAMILY_KEY_LIST:
            error_list.append({"field": key, "message": "Font tidak tersedia"})
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
TABLE_LAYOUT_FIELD_LIST = ["table_key", "hidden_list", "width_dict"]

def get_table_layout(user, table_key):
    """Layout tabel yg disimpen user. Belum pernah ngatur -> layout bawaan (ga bikin baris preferensi baru)."""
    saved_layout_dict = (user.preference.table_layout or {}).get(table_key) if user.preference else None
    return saved_layout_dict or build_default_layout(table_key)

def is_valid_width(value):
    """Lebar kolom harus angka bulat dalam batas wajar (bool ditolak walaupun di Python termasuk int)."""
    return isinstance(value, int) and not isinstance(value, bool) and TABLE_COLUMN_MIN_WIDTH <= value <= TABLE_COLUMN_MAX_WIDTH

def clean_table_layout(data_dict):
    """Cek layout dari JS. Return (table_key, layout_dict), lempar ValidationError kalau ada yg ga valid."""
    error_list = [build_error(str(key)[:50], "Field tidak dikenal") for key in data_dict if key not in TABLE_LAYOUT_FIELD_LIST]
    table_key = data_dict.get("table_key")
    column_list = TABLE_COLUMN_DICT.get(table_key) if isinstance(table_key, str) else None
    if column_list is None:
        raise ValidationError(error_list + [build_error("table_key", "Tabel tidak dikenal")])
    hideable_key_list = [column.key for column in column_list if column.is_hideable]
    column_key_list = [column.key for column in column_list]
    hidden_list = data_dict.get("hidden_list", [])
    width_dict = data_dict.get("width_dict", {})
    if not isinstance(hidden_list, list) or any(key not in hideable_key_list for key in hidden_list):
        error_list.append(build_error("hidden_list", "Kolom yang disembunyikan tidak valid"))
    if not isinstance(width_dict, dict) or any(
        key not in column_key_list or not is_valid_width(value) for key, value in width_dict.items()
    ):
        error_list.append(build_error("width_dict", f"Lebar kolom harus {TABLE_COLUMN_MIN_WIDTH}-{TABLE_COLUMN_MAX_WIDTH} px"))
    if error_list:
        raise ValidationError(error_list)
    # urutannya ngikut daftar kolom & dobel dibuang biar data yg kesimpen rapi
    clean_hidden_list = [key for key in hideable_key_list if key in hidden_list]
    return table_key, {"hidden_list": clean_hidden_list, "width_dict": width_dict}

def update_table_layout(user, data_dict):
    """Simpen layout satu tabel. Ga dicatat di audit log: cuma tampilan pribadi & bisa berubah tiap kolom digeser."""
    table_key, layout_dict = clean_table_layout(data_dict)
    preference = get_or_create_preference(user, for_write=True)
    # dict baru biar SQLAlchemy sadar kolom JSON-nya berubah
    preference.table_layout = {**(preference.table_layout or {}), table_key: layout_dict}
    db.session.commit()
    return layout_dict
