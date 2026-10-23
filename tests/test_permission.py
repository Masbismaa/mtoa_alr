"""Test menu & halaman khusus admin: kelola kategori, lihat audit log, edit link Public orang lain, panel user."""
import pytest
from app.extensions import db
from app.models import AuditLog
from tests.conftest import create_entry_as_is
from app.services.user_service import toggle_user_active, unlock_user
from app.utils.constants import ROLE_ADMIN, VISIBILITY_PUBLIC
from app.utils.exceptions import ValidationError
from app.utils.navigation import build_sidebar_section_list

def get_nav_label_list(user):
    """Helper: label menu yg bisa dibuka user (menu terkunci ga dihitung)."""
    return [
        item["label"]
        for section in build_sidebar_section_list(user, "main.home")
        for item in section["item_list"]
        if not item.get("is_locked")
    ]

def test_panel_cannot_touch_admin_account(app, admin_user, registered_user):
    """Negative: akun admin ga bisa dinonaktifin atau dibuka kuncinya dari panel."""
    other_admin = registered_user
    other_admin.role = ROLE_ADMIN
    db.session.commit()
    for action_function, argument_list in [
        (toggle_user_active, []),
        (unlock_user, []),
    ]:
        with pytest.raises(ValidationError) as error:
            action_function(admin_user, other_admin, *argument_list)
        assert error.value.error_list == [{"field": "user", "message": "Admin accounts can only be changed via the command line"}]
    assert other_admin.is_active is True

def test_user_entry_sees_admin_menu_locked(app, admin_user, registered_user):
    """Positive & negative (RBAC): Categories, Audit Logs, Users cuma kebuka buat admin; user biasa liat menunya dikunci."""
    with app.test_request_context("/"):
        user_label_list = get_nav_label_list(registered_user)
        admin_label_list = get_nav_label_list(admin_user)
        locked_item_list = [
            item for section in build_sidebar_section_list(registered_user, "main.home")
            for item in section["item_list"] if item.get("is_locked")
        ]
    for label in ("Categories", "Audit Logs", "Users"):
        assert label not in user_label_list
        assert label in admin_label_list
    assert {item["lock_reason"] for item in locked_item_list} == {"Admins only"}

def test_user_entry_cannot_open_admin_page(logged_in_client):
    """Negative (RBAC): user biasa 403 di Categories, Audit Logs, Users."""
    for url in ("/categories/", "/audit-logs/", "/users/"):
        assert logged_in_client.get(url).status_code == 403

def test_admin_can_open_admin_page(admin_client):
    """Positive: admin bisa buka Categories, Audit Logs, Users."""
    for url in ("/categories/", "/audit-logs/", "/users/"):
        assert admin_client.get(url).status_code == 200

def create_public_entry_of(user, category):
    """Helper: link Public punya user lain."""
    return create_entry_as_is(user, {
        "category_id": category.id, "title": "Portal Orang", "url": "https://orang.spindo.com",
        "address": "", "port": "", "username": "", "access_note": "", "description": "", "visibility": VISIBILITY_PUBLIC,
    })

def test_user_entry_cannot_edit_public_entry_of_other_user(logged_in_client, other_user, category_dict):
    """Negative: user biasa ga bisa edit link Public orang lain."""
    entry = create_public_entry_of(other_user, category_dict["Web"])
    assert logged_in_client.get(f"/entries/{entry.id}/edit").status_code == 403

def test_admin_can_edit_public_entry_of_other_user(admin_client, other_user, category_dict):
    """Positive: admin bisa edit link Public orang lain."""
    entry = create_public_entry_of(other_user, category_dict["Web"])
    assert admin_client.get(f"/entries/{entry.id}/edit").status_code == 200

def test_cli_set_and_unset_admin(app, admin_user, registered_user):
    """Positive & negative: naik/turun admin cuma lewat command, admin aktif terakhir ga bisa diturunin."""
    runner = app.test_cli_runner()
    result = runner.invoke(args=["set-admin", "--email", registered_user.email])
    assert result.exit_code == 0, result.output
    assert registered_user.role == ROLE_ADMIN
    result = runner.invoke(args=["unset-admin", "--email", registered_user.email])
    assert result.exit_code == 0, result.output
    assert registered_user.role != ROLE_ADMIN
    result = runner.invoke(args=["unset-admin", "--email", admin_user.email])
    assert result.exit_code != 0
    assert "at least 1 active admin" in result.output
    assert admin_user.role == ROLE_ADMIN

def test_cli_unknown_email(app):
    """Negative: email ga terdaftar -> error yg jelas."""
    result = app.test_cli_runner().invoke(args=["set-admin", "--email", "hantu@spindo.com"])
    assert result.exit_code != 0
    assert "tidak ditemukan" in result.output
