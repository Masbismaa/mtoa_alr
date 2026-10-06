"""Test grant akses per user: kelola kategori, lihat audit log, edit link Public orang lain."""
import pytest
from app.extensions import db
from app.models import AuditLog
from app.security.access_policy import has_permission
from app.services.access_entry_service import create_access_entry
from app.services.user_service import set_user_permissions, toggle_user_active, unlock_user
from app.utils.constants import (
    PERMISSION_EDIT_PUBLIC_ENTRIES,
    PERMISSION_MANAGE_CATEGORIES,
    PERMISSION_VIEW_AUDIT_LOGS,
    ROLE_ADMIN,
    VISIBILITY_PUBLIC,
)
from app.utils.exceptions import ValidationError
from app.utils.navigation import build_sidebar_section_list

def get_nav_label_list(user):
    """Helper: semua label menu yg keliatan buat user."""
    return [item["label"] for section in build_sidebar_section_list(user, "main.home") for item in section["item_list"]]

def test_admin_has_all_permission(app, admin_user):
    """Positive: admin otomatis punya semua akses tanpa di-grant."""
    assert has_permission(admin_user, PERMISSION_MANAGE_CATEGORIES)
    assert has_permission(admin_user, PERMISSION_VIEW_AUDIT_LOGS)
    assert has_permission(admin_user, PERMISSION_EDIT_PUBLIC_ENTRIES)

def test_grant_and_revoke_permission(app, admin_user, registered_user):
    """Positive: centang = dikasih, hapus centang = dicabut, kecatat di audit log."""
    assert not has_permission(registered_user, PERMISSION_MANAGE_CATEGORIES)
    set_user_permissions(admin_user, registered_user, [PERMISSION_MANAGE_CATEGORIES, PERMISSION_VIEW_AUDIT_LOGS])
    assert has_permission(registered_user, PERMISSION_MANAGE_CATEGORIES)
    assert registered_user.permission_list[0].granted_by_user_id == admin_user.id
    set_user_permissions(admin_user, registered_user, [PERMISSION_VIEW_AUDIT_LOGS])
    assert not has_permission(registered_user, PERMISSION_MANAGE_CATEGORIES)
    assert has_permission(registered_user, PERMISSION_VIEW_AUDIT_LOGS)
    audit_log = db.session.execute(
        db.select(AuditLog).filter_by(entity_type="users", entity_id=str(registered_user.id), action="update")
        .order_by(AuditLog.id.desc())
    ).scalars().first()
    assert audit_log.old_data["permission_list"] == [PERMISSION_MANAGE_CATEGORIES, PERMISSION_VIEW_AUDIT_LOGS]
    assert audit_log.new_data["permission_list"] == [PERMISSION_VIEW_AUDIT_LOGS]

def test_unknown_permission_rejected(app, admin_user, registered_user):
    """Negative: akses ngasal (misal coba nyelipin 'admin') ditolak."""
    with pytest.raises(ValidationError):
        set_user_permissions(admin_user, registered_user, ["admin"])
    assert registered_user.permission_list == []

def test_panel_cannot_touch_admin_account(app, admin_user, registered_user):
    """Negative: akun admin ga bisa diatur aksesnya, dinonaktifin, atau dibuka kuncinya dari panel."""
    other_admin = registered_user
    other_admin.role = ROLE_ADMIN
    db.session.commit()
    for action_function, argument_list in [
        (set_user_permissions, [[PERMISSION_VIEW_AUDIT_LOGS]]),
        (toggle_user_active, []),
        (unlock_user, []),
    ]:
        with pytest.raises(ValidationError) as error:
            action_function(admin_user, other_admin, *argument_list)
        assert error.value.error_list == [{"field": "user", "message": "Akun admin cuma bisa diubah lewat command"}]
    assert other_admin.is_active is True

def test_granted_user_sees_only_granted_menu(app, admin_user, registered_user):
    """Positive & negative (RBAC): menu Kelola cuma nampilin menu yg aksesnya dikasih, Users tetap khusus admin."""
    with app.test_request_context("/"):
        assert "Categories" not in get_nav_label_list(registered_user)
        set_user_permissions(admin_user, registered_user, [PERMISSION_MANAGE_CATEGORIES])
        label_list = get_nav_label_list(registered_user)
    assert "Categories" in label_list
    assert "Audit Logs" not in label_list
    assert "Users" not in label_list

def test_granted_user_can_open_categories_and_audit(logged_in_client, admin_user, registered_user):
    """Positive & negative: halaman kebuka sesuai akses yg dikasih."""
    assert logged_in_client.get("/categories/").status_code == 403
    assert logged_in_client.get("/audit-logs/").status_code == 403
    set_user_permissions(admin_user, registered_user, [PERMISSION_MANAGE_CATEGORIES, PERMISSION_VIEW_AUDIT_LOGS])
    assert logged_in_client.get("/categories/").status_code == 200
    assert logged_in_client.get("/audit-logs/").status_code == 200
    assert logged_in_client.get("/users/").status_code == 403

def test_edit_public_entry_needs_permission(logged_in_client, admin_user, registered_user, other_user, category_dict):
    """Positive & negative: edit link Public orang lain cuma kalau punya aksesnya."""
    entry = create_access_entry(other_user, {
        "category_id": category_dict["Web"].id, "title": "Portal Orang", "url": "https://orang.spindo.com",
        "address": "", "port": "", "username": "", "access_note": "", "description": "", "visibility": VISIBILITY_PUBLIC,
    })
    assert logged_in_client.get(f"/entries/{entry.id}/edit").status_code == 403
    set_user_permissions(admin_user, registered_user, [PERMISSION_EDIT_PUBLIC_ENTRIES])
    assert logged_in_client.get(f"/entries/{entry.id}/edit").status_code == 200

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
    assert "Minimal" in result.output
    assert admin_user.role == ROLE_ADMIN

def test_cli_unknown_email(app):
    """Negative: email ga terdaftar -> error yg jelas."""
    result = app.test_cli_runner().invoke(args=["set-admin", "--email", "hantu@spindo.com"])
    assert result.exit_code != 0
    assert "tidak ditemukan" in result.output
