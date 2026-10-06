"""Logika kelola user (khusus admin): daftar, cari, filter, ganti role, aktif/nonaktif, buka kunci, hapus akun."""
from sqlalchemy.orm import selectinload
from app.extensions import db
from app.models import OtpCode, User, UserPermission
from app.services.access_entry_service import count_owned_entry, delete_private_entry_list
from app.services.attachment_service import remove_stored_file_list
from app.services.audit_service import log_audit
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
    PERMISSION_LIST,
    PER_PAGE,
    VISIBILITY_PRIVATE,
    VISIBILITY_PUBLIC,
)
from app.utils.datetime_helper import to_utc_aware, utc_now
from app.utils.exceptions import ValidationError, build_error
from app.utils.query_helper import build_keyword_filter
from app.utils.sanitizer import sanitize_text
from app.utils.text_helper import normalize_email

AUDIT_USER = "users"

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

def search_users(keyword=None, role=None, status=None, page=1, per_page=PER_PAGE):
    """Cari user buat tabel admin, urut nama. Akun yg udah dihapus ga ikut."""
    query = db.select(User).options(selectinload(User.permission_list)).where(User.deleted_at.is_(None))
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
        raise ValidationError([build_error("user", "Akun admin cuma bisa diubah lewat command")])

def ensure_other_admin_left(target):
    """Minimal harus nyisa 1 admin aktif selain target."""
    other_admin_count = count_user(User.role == ROLE_ADMIN, User.is_active.is_(True), User.id != target.id)
    if other_admin_count == 0:
        raise ValidationError([build_error("user", "Minimal harus ada 1 admin aktif")])

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
        raise ValidationError([build_error("role", "Role tidak valid")])
    if new_role == target.role:
        return target
    ensure_not_self(actor, target, "Kamu tidak bisa mengubah role akunmu sendiri")
    if target.role == ROLE_ADMIN and target.is_active:
        ensure_other_admin_left(target)
    old_data_dict = build_user_admin_audit_dict(target)
    target.role = new_role
    return save_user_change(actor, target, old_data_dict)

def toggle_user_active(actor, target):
    """Aktif <-> nonaktif. User nonaktif langsung ke-logout di request berikutnya & ga bisa login."""
    ensure_not_self(actor, target, "Kamu tidak bisa menonaktifkan akunmu sendiri")
    ensure_not_admin(target)
    old_data_dict = build_user_admin_audit_dict(target)
    target.is_active = not target.is_active
    return save_user_change(actor, target, old_data_dict)

def unlock_user(actor, target):
    """Buka kunci akun yg kekunci gara-gara kebanyakan salah password/OTP."""
    ensure_not_admin(target)
    if get_user_status(target) != USER_STATUS_LOCKED:
        raise ValidationError([build_error("user", "Akun ini tidak sedang terkunci")])
    old_data_dict = build_user_admin_audit_dict(target)
    target.locked_until = None
    target.failed_login_count = 0
    return save_user_change(actor, target, old_data_dict)

# HAK AKSES (GRANT)
def get_permission_key_list(user):
    """Akses yg dipunya user, urut sesuai PERMISSION_LIST."""
    owned_key_set = {permission.permission_key for permission in user.permission_list}
    return [permission_key for permission_key in PERMISSION_LIST if permission_key in owned_key_set]

def set_user_permissions(actor, target, permission_key_list):
    """Simpan akses user persis sesuai yg dicentang: yg baru ditambah, yg dicabut dihapus."""
    ensure_not_admin(target)
    new_key_set = set(permission_key_list or [])
    if not new_key_set.issubset(PERMISSION_LIST):
        raise ValidationError([build_error("permission", "Ada akses yang tidak dikenal")])
    old_key_list = get_permission_key_list(target)
    if new_key_set == set(old_key_list):
        return target
    target.permission_list = [
        permission for permission in target.permission_list if permission.permission_key in new_key_set
    ] + [
        UserPermission(permission_key=permission_key, granted_by_user_id=actor.id)
        for permission_key in PERMISSION_LIST
        if permission_key in new_key_set and permission_key not in old_key_list
    ]
    log_audit(
        AUDIT_ACTION_UPDATE, AUDIT_USER, entity_id=target.id,
        old_data_dict={"permission_list": old_key_list},
        new_data_dict={"permission_list": get_permission_key_list(target)}, user=actor,
    )
    db.session.commit()
    return target

# HAPUS AKUN
def ensure_delete_confirmed(target, confirm_email):
    """Admin wajib ngetik ulang email target biar ga salah hapus."""
    if normalize_email(confirm_email) != target.email:
        raise ValidationError([build_error("confirm_email", "Email konfirmasi tidak cocok dengan email akun ini")])

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
    target.failed_login_count = 0
    target.locked_until = None
    target.deleted_at = utc_now()
    target.preference = None

def delete_user_account(actor, target, confirm_email):
    """Hapus akun: link Private + lampirannya dihapus, link Public tetep ada, group dilepas, akses dicabut, data diri dianonimkan."""
    ensure_not_self(actor, target, "Kamu tidak bisa menghapus akunmu sendiri")
    ensure_not_admin(target)
    if target.deleted_at is not None:
        raise ValidationError([build_error("user", "Akun ini sudah dihapus")])
    ensure_delete_confirmed(target, confirm_email)
    old_data_dict = {
        "email": target.email, "full_name": target.full_name, "department": target.department,
        "job_title": target.job_title, "role": target.role, "is_active": target.is_active,
        "permission_list": get_permission_key_list(target),
    }
    group_summary_dict = release_user_group_list(actor, target)
    private_entry_count, stored_filename_list = delete_private_entry_list(actor, target)
    target.permission_list = []
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
