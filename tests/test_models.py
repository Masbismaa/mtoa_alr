"""Unit test model users, categories, dan user_preferences (SR-01, SR-02, SR-17)."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Category, User, UserPreference
from app.utils.constants import DEFAULT_ACCENT_COLOR, ROLE_USER_ENTRY, THEME_MODE_LIGHT


def build_user(email="user.test@spindo.com", role=None):
    """Helper: membuat objek User contoh untuk test (dipakai ulang, DRY)."""
    user = User(email=email, full_name="User Test", department="ICT", job_title="Staff", password_hash="hash-dummy")
    if role:
        user.role = role
    return user


def test_create_user_normalizes_email(app):
    """Positive: email disimpan tanpa spasi dan dalam huruf kecil."""
    user = build_user(email="  User.Test@Spindo.COM ")
    db.session.add(user)
    db.session.commit()
    assert user.email == "user.test@spindo.com"


def test_user_default_role_and_active_status(app):
    """Positive: user baru otomatis ber-role user_entry, aktif, dan punya created_at."""
    user = build_user()
    db.session.add(user)
    db.session.commit()
    assert user.role == ROLE_USER_ENTRY
    assert user.is_active is True
    assert user.created_at is not None


def test_user_duplicate_email_is_rejected(app):
    """Negative: email yang sama (beda huruf besar/kecil) tidak boleh terdaftar dua kali."""
    db.session.add(build_user())
    db.session.commit()
    db.session.add(build_user(email="USER.TEST@spindo.com"))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_user_invalid_role_is_rejected(app):
    """Negative (security): role di luar admin/user_entry ditolak oleh database."""
    db.session.add(build_user(role="superadmin"))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_user_preference_default_values(app):
    """Positive: preferensi baru memakai tema light, warna aksen default, dan tidak compact."""
    user = build_user()
    user.preference = UserPreference()
    db.session.add(user)
    db.session.commit()
    assert user.preference.theme_mode == THEME_MODE_LIGHT
    assert user.preference.accent_color == DEFAULT_ACCENT_COLOR
    assert user.preference.is_compact_view is False


def test_user_cannot_have_two_preferences(app):
    """Negative: satu user hanya boleh punya satu baris preferensi."""
    user = build_user()
    db.session.add(user)
    db.session.commit()
    db.session.add_all([UserPreference(user_id=user.id), UserPreference(user_id=user.id)])
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_category_name_must_be_unique(app):
    """Negative: nama kategori tidak boleh duplikat."""
    db.session.add(Category(name="Web"))
    db.session.commit()
    db.session.add(Category(name="Web"))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()