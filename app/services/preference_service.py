"""Ambil & ubah preferensi tampilan user."""
from app.extensions import db
from app.models import UserPreference
from app.services.audit_service import log_audit
from app.utils.constants import (
    ACCENT_KEY_BY_HEX_DICT,
    AUDIT_ACTION_UPDATE,
    DEFAULT_ACCENT_KEY,
    FONT_FAMILY_KEY_LIST,
    THEME_MODE_LIST,
)
from app.utils.exceptions import ValidationError

# cuma field ini yg boleh diubah lewat API, sisanya ditolak
PREFERENCE_FIELD_LIST = ["theme_mode", "accent_color", "is_compact_view", "font_family"]

def get_or_create_preference(user):
    """Ambil preferensi user, kalau belum ada langsung dibikinin yg default."""
    if user.preference is None:
        user.preference = UserPreference()
        db.session.commit()
    return user.preference

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

    preference = get_or_create_preference(user)
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
    return preference