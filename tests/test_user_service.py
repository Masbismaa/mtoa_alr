"""Test logika kelola user bagian 1: cari, filter, status, ringkasan."""
from datetime import timedelta
from app.extensions import db
from app.services.auth_service import register_user
from app.services.user_service import build_user_summary, get_user_status, search_users
from app.utils.constants import ROLE_ADMIN, USER_STATUS_ACTIVE, USER_STATUS_INACTIVE, USER_STATUS_LOCKED
from app.utils.datetime_helper import utc_now

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