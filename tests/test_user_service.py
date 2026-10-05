"""Test logika kelola user: cari, filter, status, ringkasan, ganti role, aktif/nonaktif, buka kunci."""
from datetime import timedelta
import pytest
from app.extensions import db
from app.models import AuditLog
from app.services.auth_service import authenticate_user, register_user
from app.services.user_service import (
    build_user_summary,
    change_user_role,
    get_user_status,
    search_users,
    toggle_user_active,
    unlock_user,
)
from app.utils.constants import (
    ROLE_ADMIN,
    ROLE_USER_ENTRY,
    USER_STATUS_ACTIVE,
    USER_STATUS_INACTIVE,
    USER_STATUS_LOCKED,
)
from app.utils.datetime_helper import utc_now
from app.utils.exceptions import AuthError, ValidationError
def create_user(email, full_name, department="ICT", job_title="Staff", role=None):
    """Helper: daftarin user contoh."""
    extra_dict = {"role": role} if role else {}
    return register_user(
        email=email, password="PasswordKuat123", full_name=full_name,
        department=department, job_title=job_title, **extra_dict,
    )

def get_email_list(pagination):
    """Helper: email hasil pencarian."""
    return [user.email for user in pagination.items]

def test_search_by_name_department_and_email(app):
    """Positive: kata kunci nyari ke nama, email, departemen, jabatan (huruf besar/kecil sama aja)."""
    create_user("andi@spindo.com", "Andi Saputra", department="Finance")
    create_user("budi@spindo.com", "Budi Santoso", job_title="Network Engineer")
    assert get_email_list(search_users(keyword="andi")) == ["andi@spindo.com"]
    assert get_email_list(search_users(keyword="FINANCE")) == ["andi@spindo.com"]
    assert get_email_list(search_users(keyword="network")) == ["budi@spindo.com"]

def test_search_keyword_wildcard_is_literal(app):
    """Negative: % di kata kunci dianggap huruf biasa, bukan wildcard."""
    create_user("andi@spindo.com", "Andi Saputra")
    assert search_users(keyword="%").total == 0

def test_filter_by_role(app, admin_user):
    """Positive: filter role cuma nampilin role itu."""
    create_user("andi@spindo.com", "Andi Saputra")
    assert get_email_list(search_users(role=ROLE_ADMIN)) == [admin_user.email]
    assert search_users(role="hacker").total == 2

def test_status_follows_active_and_lock(app):
    """Positive: status nonaktif > terkunci > aktif, filter SQL-nya sama kayak tampilan."""
    active_user = create_user("aktif@spindo.com", "User Aktif")
    locked_user = create_user("kunci@spindo.com", "User Terkunci")
    inactive_user = create_user("mati@spindo.com", "User Nonaktif")
    locked_user.locked_until = utc_now() + timedelta(minutes=10)
    inactive_user.is_active = False
    inactive_user.locked_until = utc_now() + timedelta(minutes=10)
    db.session.commit()
    assert get_user_status(active_user) == USER_STATUS_ACTIVE
    assert get_user_status(locked_user) == USER_STATUS_LOCKED
    assert get_user_status(inactive_user) == USER_STATUS_INACTIVE
    assert get_email_list(search_users(status=USER_STATUS_ACTIVE)) == ["aktif@spindo.com"]
    assert get_email_list(search_users(status=USER_STATUS_LOCKED)) == ["kunci@spindo.com"]
    assert get_email_list(search_users(status=USER_STATUS_INACTIVE)) == ["mati@spindo.com"]

def test_expired_lock_counts_as_active(app):
    """Positive: kunci yg udah lewat waktunya dianggap aktif lagi."""
    user = create_user("lewat@spindo.com", "Kunci Lewat")
    user.locked_until = utc_now() - timedelta(minutes=1)
    db.session.commit()
    assert get_user_status(user) == USER_STATUS_ACTIVE
    assert get_email_list(search_users(status=USER_STATUS_ACTIVE)) == ["lewat@spindo.com"]

def test_user_summary(app, admin_user):
    """Positive: ringkasan total, admin, terkunci, nonaktif."""
    inactive_user = create_user("mati@spindo.com", "User Nonaktif")
    inactive_user.is_active = False
    db.session.commit()
    assert build_user_summary() == {"total": 2, "admin": 1, "locked": 0, "inactive": 1}

def test_pagination(app):
    """Positive: hasil dipecah per halaman, urut nama."""
    for number in range(3):
        create_user(f"user{number}@spindo.com", f"User {number}")
    first_page = search_users(page=1, per_page=2)
    assert first_page.total == 3
    assert get_email_list(first_page) == ["user0@spindo.com", "user1@spindo.com"]
    assert get_email_list(search_users(page=2, per_page=2)) == ["user2@spindo.com"]

def test_change_role_logged(app, admin_user, registered_user):
    """Positive: admin ganti role user lain, kecatat di audit log."""
    change_user_role(admin_user, registered_user, ROLE_ADMIN)
    assert registered_user.role == ROLE_ADMIN
    audit_log = db.session.execute(
        db.select(AuditLog).filter_by(entity_type="users", entity_id=str(registered_user.id), action="update")
    ).scalar_one()
    assert audit_log.old_data["role"] == ROLE_USER_ENTRY
    assert audit_log.new_data["role"] == ROLE_ADMIN

def test_cannot_change_own_role(app, admin_user):
    """Negative: admin ga bisa nurunin role-nya sendiri."""
    with pytest.raises(ValidationError):
        change_user_role(admin_user, admin_user, ROLE_USER_ENTRY)
    assert admin_user.role == ROLE_ADMIN

def test_invalid_role_rejected(app, admin_user, registered_user):
    """Negative: role ngasal ditolak."""
    with pytest.raises(ValidationError):
        change_user_role(admin_user, registered_user, "superadmin")
    assert registered_user.role == ROLE_USER_ENTRY

def test_last_active_admin_cannot_be_demoted(app, admin_user):
    """Negative: admin aktif terakhir ga bisa diturunin lewat command."""
    with pytest.raises(ValidationError) as error:
        change_user_role(None, admin_user, ROLE_USER_ENTRY)
    assert error.value.error_list == [{"field": "user", "message": "Minimal harus ada 1 admin aktif"}]
    assert admin_user.role == ROLE_ADMIN

def test_deactivated_user_cannot_login(app, admin_user, registered_user, user_password):
    """Positive & negative: user dinonaktifin ga bisa login, diaktifin lagi bisa."""
    toggle_user_active(admin_user, registered_user)
    assert registered_user.is_active is False
    with pytest.raises(AuthError):
        authenticate_user(registered_user.email, user_password)
    toggle_user_active(admin_user, registered_user)
    assert authenticate_user(registered_user.email, user_password).id == registered_user.id

def test_cannot_deactivate_self(app, admin_user):
    """Negative: admin ga bisa nonaktifin akunnya sendiri."""
    with pytest.raises(ValidationError):
        toggle_user_active(admin_user, admin_user)
    assert admin_user.is_active is True

def test_unlock_user(app, admin_user, registered_user):
    """Positive: buka kunci akun -> status aktif lagi, hitungan gagal di-reset."""
    registered_user.locked_until = utc_now() + timedelta(minutes=10)
    registered_user.failed_login_count = 3
    db.session.commit()
    unlock_user(admin_user, registered_user)
    assert get_user_status(registered_user) == USER_STATUS_ACTIVE
    assert registered_user.failed_login_count == 0

def test_unlock_not_locked_rejected(app, admin_user, registered_user):
    """Negative: akun yg ga kekunci ga bisa dibuka kuncinya."""
    with pytest.raises(ValidationError) as error:
        unlock_user(admin_user, registered_user)
    assert error.value.error_list == [{"field": "user", "message": "Akun ini tidak sedang terkunci"}]
