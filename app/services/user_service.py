"""Logika kelola user (khusus admin). Bagian 1: daftar, cari, filter, ringkasan."""
from app.extensions import db
from app.models import User
from app.utils.constants import (
    MAX_SEARCH_KEYWORD_LENGTH,
    ROLE_ADMIN,
    ROLE_LIST,
    USER_PER_PAGE,
    USER_STATUS_ACTIVE,
    USER_STATUS_INACTIVE,
    USER_STATUS_LOCKED,
)
from app.utils.datetime_helper import to_utc_aware, utc_now
from app.utils.query_helper import build_keyword_filter
from app.utils.sanitizer import sanitize_text

def get_user_status(user):
    """Status akun buat ditampilin: nonaktif > terkunci > aktif."""
    if not user.is_active:
        return USER_STATUS_INACTIVE
    if user.locked_until is not None and to_utc_aware(user.locked_until) > utc_now():
        return USER_STATUS_LOCKED
    return USER_STATUS_ACTIVE

def build_status_condition(status):
    """Kondisi SQL buat filter status. Logikanya harus sama kayak get_user_status."""
    now = utc_now()
    is_locked_condition = db.and_(User.locked_until.is_not(None), User.locked_until > now)
    if status == USER_STATUS_INACTIVE:
        return User.is_active.is_(False)
    if status == USER_STATUS_LOCKED:
        return db.and_(User.is_active.is_(True), is_locked_condition)
    if status == USER_STATUS_ACTIVE:
        return db.and_(User.is_active.is_(True), db.not_(is_locked_condition))
    return None

def search_users(keyword=None, role=None, status=None, page=1, per_page=USER_PER_PAGE):
    """Cari user buat tabel admin, urut nama."""
    query = db.select(User)
    clean_keyword = sanitize_text(keyword, max_length=MAX_SEARCH_KEYWORD_LENGTH)
    if clean_keyword:
        search_column_list = [User.email, User.full_name, User.department, User.job_title]
        query = query.where(build_keyword_filter(search_column_list, clean_keyword))
    if role in ROLE_LIST:
        query = query.where(User.role == role)
    status_condition = build_status_condition(status)
    if status_condition is not None:
        query = query.where(status_condition)
    query = query.order_by(db.func.lower(User.full_name), User.id)
    return db.paginate(query, page=page, per_page=per_page, error_out=False)

def count_user(*condition_list):
    """Hitung user dgn kondisi tertentu (boleh kosong = semua)."""
    return db.session.scalar(db.select(db.func.count(User.id)).where(*condition_list))

def build_user_summary():
    """Angka ringkas di atas tabel: total, admin, terkunci, nonaktif."""
    return {
        "total": count_user(),
        "admin": count_user(User.role == ROLE_ADMIN),
        "locked": count_user(build_status_condition(USER_STATUS_LOCKED)),
        "inactive": count_user(build_status_condition(USER_STATUS_INACTIVE)),
    }