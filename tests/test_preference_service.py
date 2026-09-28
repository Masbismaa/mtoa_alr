"""Test preferensi tampilan."""
import pytest

from app.extensions import db
from app.models import AuditLog, User
from app.services.preference_service import build_ui_preference_dict, get_or_create_preference, update_preference
from app.utils.constants import AUDIT_ACTION_UPDATE, THEME_MODE_DARK
from app.utils.exceptions import ValidationError

def count_update_audit():
    """Helper: hitung audit log aksi update."""
    return db.session.execute(db.select(db.func.count(AuditLog.id)).filter_by(action=AUDIT_ACTION_UPDATE)).scalar()

def assert_invalid_field(user, data_dict, expected_field):
    """Helper: pastiin update ditolak & field yg salah kesebut di error_list."""
    with pytest.raises(ValidationError) as error_info:
        update_preference(user, data_dict)
    field_list = [error_dict["field"] for error_dict in error_info.value.error_list]
    assert expected_field in field_list

def test_get_or_create_preference_creates_missing(app):
    """Positive: user tanpa preferensi otomatis dibikinin yg default."""
    user = User(email="tanpa.pref@spindo.com", full_name="Tanpa Pref", department="ICT", job_title="Staff", password_hash="hash-dummy")
    db.session.add(user)
    db.session.commit()
    preference = get_or_create_preference(user)
    assert preference.id is not None
    assert preference.theme_mode == "light"

def test_build_ui_preference_dict_maps_accent_key(app, registered_user):
    """Positive: hex warna default diterjemahin jadi key 'blue' buat CSS."""
    ui_preference_dict = build_ui_preference_dict(registered_user.preference)
    assert ui_preference_dict["accent_key"] == "blue"
    assert ui_preference_dict["font_family"] == "system"

def test_update_preference_partial_success(app, registered_user):
    """Positive: ubah sebagian field, hex dirapihin jadi huruf kecil, kecatat di audit."""
    preference = update_preference(registered_user, {"theme_mode": "dark", "accent_color": "#FFD23F"})
    assert preference.theme_mode == THEME_MODE_DARK
    assert preference.accent_color == "#ffd23f"
    assert count_update_audit() == 1

def test_update_preference_invalid_theme(app, registered_user):
    """Negative: mode selain light/dark ditolak."""
    assert_invalid_field(registered_user, {"theme_mode": "neon"}, "theme_mode")

def test_update_preference_invalid_accent(app, registered_user):
    """Negative (security): warna di luar daftar ditolak (ga bisa nyuntik CSS)."""
    assert_invalid_field(registered_user, {"accent_color": "red;background:url(x)"}, "accent_color")

def test_update_preference_unknown_field(app, registered_user):
    """Negative (security): field asing kayak 'role' ga bisa diselipin."""
    assert_invalid_field(registered_user, {"role": "admin"}, "role")

def test_update_preference_compact_must_be_bool(app, registered_user):
    """Negative: is_compact_view wajib true/false beneran, bukan teks."""
    assert_invalid_field(registered_user, {"is_compact_view": "yes"}, "is_compact_view")

def test_update_preference_empty_data(app, registered_user):
    """Negative: data kosong ditolak."""
    assert_invalid_field(registered_user, {}, None)

def test_update_preference_same_value_no_audit(app, registered_user):
    """Positive: kalau ga ada yg berubah, ga usah nyatet audit."""
    update_preference(registered_user, {"theme_mode": "light"})
    assert count_update_audit() == 0