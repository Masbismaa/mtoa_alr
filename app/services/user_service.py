"""Logika kelola user (khusus admin): daftar, cari, filter, ganti role, aktif/nonaktif, buka kunci, hapus akun."""
from app.extensions import db
from app.models import OtpCode, User
from app.security import auth_throttle
from app.services.access_entry_service import count_owned_entry, delete_private_entry_list
from app.services.attachment_service import remove_stored_file_list
from app.services.audit_service import log_audit
from app.services.auth_service import is_account_locked
from app.services.group_service import find_group_successor, list_owned_group, release_user_group_list
from app.utils.constants import (
    AUDIT_ACTION_DELETE,
    AUDIT_ACTION_UPDATE,
    DELETED_USER_EMAIL_DOMAIN,
    DELETED_USER_NAME,
    DELETED_USER_PROFILE_TEXT,
    MAX_SEARCH_KEYWORD_LENGTH,
    ROLE_ADMIN,
    ROLE_LIST,
    UNUSABLE_PASSWORD_HASH,
    USER_STATUS_ACTIVE,
    USER_STATUS_INACTIVE,
    USER_STATUS_LOCKED,
    PER_PAGE,
    VISIBILITY_PRIVATE,
    VISIBILITY_PUBLIC,
)
from app.utils.data_table import build_order_list
from app.utils.datetime_helper import utc_now
from app.utils.exceptions import ValidationError, build_error
from app.utils.query_helper import build_keyword_filter
from app.utils.selection import apply_condition_list, build_date_range_filter, build_text_selection_filter
from app.utils.sanitizer import sanitize_text
from app.utils.text_helper import normalize_email

AUDIT_USER = "users"

def get_user_status(user):
    """Status akun buat ditampilin: nonaktif > terkunci > aktif."""
    if not user.is_active:
        return USER_STATUS_INACTIVE
    if is_account_locked(user):
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

def apply_user_selection(query, selection):
    """Tempel kriteria Select Screen (nama/email, departemen, role, status, tanggal daftar) ke query user."""
    status_condition_list = [build_status_condition(status) for status in selection["status_list"]]
    return apply_condition_list(query, [
        build_text_selection_filter([User.full_name, User.email], selection["name"]),
        build_text_selection_filter([User.department, User.job_title], selection["department"]),
        User.role.in_(selection["role_list"]) if selection["role_list"] else None,
        db.or_(*status_condition_list) if status_condition_list else None,
        build_date_range_filter(User.created_at, *selection["created_range"]),
    ])

# kolom yg bisa diurutin di tabel Users (kunci = key kolom di table_schema)
USER_SORT_COLUMN_DICT = {
    "name": db.func.lower(User.full_name),
    "department": db.func.lower(User.department),
    "role": User.role,
    "last_login": User.last_login_at,
    "created": User.created_at,
}

def search_users(keyword=None, role=None, status=None, page=1, per_page=PER_PAGE, selection=None, sort=None):
    """Cari user buat tabel admin, defaultnya urut nama. Akun yg udah dihapus ga ikut."""
    query = db.select(User).where(User.deleted_at.is_(None))
    clean_keyword = sanitize_text(keyword, max_length=MAX_SEARCH_KEYWORD_LENGTH)
    if clean_keyword:
        search_column_list = [User.email, User.full_name, User.department, User.job_title]
        query = query.where(build_keyword_filter(search_column_list, clean_keyword))
    if role in ROLE_LIST:
        query = query.where(User.role == role)
    status_condition = build_status_condition(status)
    if status_condition is not None:
        query = query.where(status_condition)
    if selection:
        query = apply_user_selection(query, selection)
    default_order_list = [db.func.lower(User.full_name), User.id]
    query = query.order_by(*build_order_list(sort, USER_SORT_COLUMN_DICT, default_order_list, User.id))
    return db.paginate(query, page=page, per_page=per_page, error_out=False)

def count_user(*condition_list):
    """Hitung user yg belum dihapus dgn kondisi tertentu (boleh kosong = semua)."""
    return db.session.scalar(db.select(db.func.count(User.id)).where(User.deleted_at.is_(None), *condition_list))

def build_user_summary():
    """Angka ringkas di atas tabel: total, admin, terkunci, nonaktif."""
    return {
        "total": count_user(),
        "admin": count_user(User.role == ROLE_ADMIN),
        "locked": count_user(build_status_condition(USER_STATUS_LOCKED)),
        "inactive": count_user(build_status_condition(USER_STATUS_INACTIVE)),
    }

# ganti role aun
def get_user(user_id):
    """Satu user, None kalau ga ada."""
    return db.session.get(User, user_id)

def build_user_admin_audit_dict(user):
    """Data akun yg diubah admin, buat audit log."""
    return {"role": user.role, "is_active": user.is_active, "is_locked": get_user_status(user) == USER_STATUS_LOCKED}

def ensure_not_self(actor, target, message):
    """Admin ga boleh ngubah akunnya sendiri dari panel. actor None = dari command (CLI)."""
    if actor is not None and actor.id == target.id:
        raise ValidationError([build_error("user", message)])

def ensure_not_admin(target):
    """Akun admin cuma bisa diubah lewat command, bukan dari panel."""
    if target.role == ROLE_ADMIN:
        raise ValidationError([build_error("user", "Admin accounts can only be changed via the command line")])

def ensure_other_admin_left(target):
    """Minimal harus nyisa 1 admin aktif selain target. Baris semua admin aktif dikunci dulu (FOR UPDATE), jadi
    2 perintah barengan yg nurunin 2 admin beda diproses satu-satu & ga bisa sama-sama liat "masih ada admin lain".
    (FOR UPDATE ga boleh bareng COUNT di PostgreSQL, makanya id-nya yg diambil)"""
    admin_id_list = db.session.scalars(
        db.select(User.id).where(User.deleted_at.is_(None), User.role == ROLE_ADMIN, User.is_active.is_(True))
        .with_for_update()
    ).all()
    if not [admin_id for admin_id in admin_id_list if admin_id != target.id]:
        raise ValidationError([build_error("user", "There must be at least 1 active admin")])

def save_user_change(actor, target, old_data_dict):
    """Catat perubahan ke audit log terus simpan."""
    log_audit(
        AUDIT_ACTION_UPDATE, AUDIT_USER, entity_id=target.id,
        old_data_dict=old_data_dict, new_data_dict=build_user_admin_audit_dict(target), user=actor,
    )
    db.session.commit()
    return target

def change_user_role(actor, target, new_role):
    """Ganti role user, cuma dipanggil dari command set-admin/unset-admin (actor None)."""
    if new_role not in ROLE_LIST:
        raise ValidationError([build_error("role", "Invalid role")])
    if new_role == target.role:
        return target
    ensure_not_self(actor, target, "You can't change the role of your own account")
    if target.role == ROLE_ADMIN and target.is_active:
        ensure_other_admin_left(target)
    old_data_dict = build_user_admin_audit_dict(target)
    target.role = new_role
    return save_user_change(actor, target, old_data_dict)

def toggle_user_active(actor, target):
    """Aktif <-> nonaktif. User nonaktif langsung ke-logout di request berikutnya & ga bisa login."""
    ensure_not_self(actor, target, "You can't deactivate your own account")
    ensure_not_admin(target)
    old_data_dict = build_user_admin_audit_dict(target)
    target.is_active = not target.is_active
    db.session.execute(db.update(User).where(User.id == target.id)
                       .values(session_version=User.session_version + 1))
    return save_user_change(actor, target, old_data_dict)

def unlock_user(actor, target):
    """Buka kunci akun yg kekunci gara-gara kebanyakan salah password/OTP."""
    ensure_not_admin(target)
    if get_user_status(target) != USER_STATUS_LOCKED:
        raise ValidationError([build_error("user", "This account is not locked")])
    old_data_dict = build_user_admin_audit_dict(target)
    target.locked_until = None
    target.failed_login_count = 0
    result = save_user_change(actor, target, old_data_dict)
    # blokir percobaan login per email ikut dibuka, kalau ngga user tetep ketahan sampe 15 menit
    auth_throttle.clear_login_failure(target.email)
    return result

# HAPUS AKUN
def ensure_delete_confirmed(target, confirm_email):
    """Admin wajib ngetik ulang email target biar ga salah hapus."""
    if normalize_email(confirm_email) != target.email:
        raise ValidationError([build_error("confirm_email", "The confirmation email doesn't match this account's email")])

def build_delete_preview(target):
    """Apa aja yg bakal kena kalau akun ini dihapus, ditampilin sebelum admin konfirmasi."""
    return {
        "private_entry_count": count_owned_entry(target, VISIBILITY_PRIVATE),
        "public_entry_count": count_owned_entry(target, VISIBILITY_PUBLIC),
        "owned_group_list": [
            {"group": group, "successor": find_group_successor(group, target.id)} for group in list_owned_group(target)
        ],
    }

def anonymize_user(target):
    """Ganti data diri jadi anonim + kunci login. Email asli jadi bebas dipake daftar lagi."""
    target.email = f"deleted-{target.id}@{DELETED_USER_EMAIL_DOMAIN}"
    target.full_name = DELETED_USER_NAME
    target.department = DELETED_USER_PROFILE_TEXT
    target.job_title = DELETED_USER_PROFILE_TEXT
    target.password_hash = UNUSABLE_PASSWORD_HASH
    target.is_active = False
    db.session.execute(db.update(User).where(User.id == target.id)
                       .values(session_version=User.session_version + 1))
    target.failed_login_count = 0
    target.locked_until = None
    target.deleted_at = utc_now()
    target.preference = None

def delete_user_account(actor, target, confirm_email):
    """Hapus akun: link Private + lampirannya dihapus, link Public tetep ada, group dilepas, data diri dianonimkan."""
    ensure_not_self(actor, target, "You can't delete your own account")
    ensure_not_admin(target)
    if target.deleted_at is not None:
        raise ValidationError([build_error("user", "This account has already been deleted")])
    ensure_delete_confirmed(target, confirm_email)
    old_data_dict = {
        "email": target.email, "full_name": target.full_name, "department": target.department,
        "job_title": target.job_title, "role": target.role, "is_active": target.is_active,
    }
    group_summary_dict = release_user_group_list(actor, target)
    private_entry_count, stored_filename_list = delete_private_entry_list(actor, target)
    db.session.execute(db.delete(OtpCode).where(OtpCode.user_id == target.id))
    anonymize_user(target)
    log_audit(
        AUDIT_ACTION_DELETE, AUDIT_USER, entity_id=target.id, old_data_dict=old_data_dict,
        new_data_dict={"deleted_private_entry_count": private_entry_count, **group_summary_dict}, user=actor,
    )
    db.session.commit()
    # file lampiran baru dihapus setelah database aman ke-commit
    remove_stored_file_list(stored_filename_list)
    return target
