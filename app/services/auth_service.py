"""Logika register, login (password), dan OTP. Route tinggal manggil fungsi di sini."""
from datetime import timedelta
from functools import lru_cache

from flask import current_app

from app.extensions import db
from app.models import OtpCode, User, UserPreference
from app.security.otp_service import generate_otp_code, hash_otp_code, is_otp_code_match
from app.security.password_service import hash_password, verify_password
from app.services.audit_service import log_audit
from app.services.notification_service import send_otp_code
from app.utils.constants import (
    AUDIT_ACTION_CREATE,
    AUDIT_ACTION_LOGIN,
    AUDIT_ACTION_LOGIN_FAILED,
    LOGIN_LOCK_MINUTES,
    LOGIN_MAX_FAILED_COUNT,
    OTP_EXPIRE_MINUTES,
    OTP_MAX_ATTEMPT_COUNT,
    OTP_RESEND_COOLDOWN_SECONDS,
    ROLE_USER_ENTRY,
)
from app.utils.datetime_helper import to_utc_aware, utc_now
from app.utils.exceptions import AuthError
from app.utils.sanitizer import sanitize_text
from app.utils.text_helper import normalize_email

# pesan login gagal dibikin sama semua, biar orang ga bisa nebak email mana yg terdaftar
GENERIC_LOGIN_ERROR = "Email atau password salah"
ACCOUNT_LOCKED_ERROR = f"Akun dikunci sementara karena terlalu banyak percobaan. Coba lagi dalam {LOGIN_LOCK_MINUTES} menit."
INACTIVE_ACCOUNT_ERROR = "Akun ini sudah tidak aktif, hubungi admin untuk mengaktifkan kembali."


# REGISTER

def is_allowed_email_domain(email):
    """Cek email pake domain yg diizinin (default @spindo.com)."""
    allowed_domain = current_app.config["ALLOWED_EMAIL_DOMAIN"].lower()
    return email.count("@") == 1 and email.endswith(f"@{allowed_domain}")


def build_user_audit_dict(user):
    """Data user yg dicatat ke audit log (tanpa password)."""
    return {
        "email": user.email,
        "full_name": user.full_name,
        "department": user.department,
        "job_title": user.job_title,
        "role": user.role,
    }


def register_user(email, password, full_name, department, job_title, role=ROLE_USER_ENTRY):
    """Bikin akun baru + preferensi default, terus dicatat ke audit log.

    Halaman register selalu pake role default (user_entry).
    Role admin cuma bisa lewat perintah CLI create-admin.
    """
    clean_email = normalize_email(email)

    # cuma email kantor yg boleh daftar
    if not is_allowed_email_domain(clean_email):
        raise AuthError(f"Email wajib pakai domain @{current_app.config['ALLOWED_EMAIL_DOMAIN']}")

    # cek email udah kepake belum (cukup ambil id-nya aja, lebih ringan)
    is_email_taken = db.session.execute(db.select(User.id).filter_by(email=clean_email)).first() is not None
    if is_email_taken:
        raise AuthError("Email sudah terdaftar")

    # bersihin data profil dari tag HTML dkk
    clean_full_name = sanitize_text(full_name, max_length=150)
    clean_department = sanitize_text(department, max_length=100)
    clean_job_title = sanitize_text(job_title, max_length=100)
    if not all([clean_full_name, clean_department, clean_job_title]):
        raise AuthError("Nama, departemen, dan jabatan wajib diisi")

    # hash password (sekalian dicek panjang minimalnya)
    try:
        password_hash = hash_password(password)
    except ValueError as error:
        raise AuthError(str(error)) from error

    user = User(
        email=clean_email,
        full_name=clean_full_name,
        department=clean_department,
        job_title=clean_job_title,
        role=role,
        password_hash=password_hash,
    )
    # langsung kasih preferensi tampilan default
    user.preference = UserPreference()
    db.session.add(user)
    # flush biar user.id udah keisi buat dicatat ke audit
    db.session.flush()

    log_audit(AUDIT_ACTION_CREATE, "users", entity_id=user.id, new_data_dict=build_user_audit_dict(user), user=user)
    db.session.commit()
    return user


# LOGIN LANGKAH 1: EMAIL + PASSWORD

@lru_cache(maxsize=1)
def get_dummy_password_hash():
    """Hash palsu buat email yg ga terdaftar, biar waktu responnya sama kayak email asli."""
    return hash_password("dummy-password-cuma-buat-timing-123")


def is_account_locked(user):
    """True kalau akun lagi dikunci gara-gara kebanyakan salah password."""
    return user.locked_until is not None and to_utc_aware(user.locked_until) > utc_now()


def register_failed_login(user):
    """Tambah hitungan salah password. Kalau nyampe batas, kunci akunnya."""
    user.failed_login_count += 1
    if user.failed_login_count >= LOGIN_MAX_FAILED_COUNT:
        user.locked_until = utc_now() + timedelta(minutes=LOGIN_LOCK_MINUTES)
        # hitungan di-reset, nanti mulai dari 0 lagi pas kunci udah kebuka
        user.failed_login_count = 0


def authenticate_user(email, password):
    """Cek email + password. Return User kalau bener, lempar Auth-Error kalau salah."""
    clean_email = normalize_email(email)
    user = db.session.execute(db.select(User).filter_by(email=clean_email)).scalar_one_or_none()

    # email ga terdaftar: tetep jalanin verifikasi palsu biar waktunya sama
    if user is None:
        verify_password(get_dummy_password_hash(), password or "")
        log_audit(AUDIT_ACTION_LOGIN_FAILED, "users", actor_email=clean_email[:255], is_commit=True)
        raise AuthError(GENERIC_LOGIN_ERROR)

    # akun lagi dikunci
    if is_account_locked(user):
        log_audit(
            AUDIT_ACTION_LOGIN_FAILED, "users", entity_id=user.id, user=user,
            new_data_dict={"reason": "account_locked"}, is_commit=True,
        )
        raise AuthError(ACCOUNT_LOCKED_ERROR)

    # akun nonaktif atau password salah -> pesannya tetep sama
    if not user.is_active or not verify_password(user.password_hash, password):
        register_failed_login(user)
        failed_reason = "inactive" if not user.is_active else "wrong_password"
        log_audit(AUDIT_ACTION_LOGIN_FAILED, "users", entity_id=user.id, user=user, new_data_dict={"reason": failed_reason})
        db.session.commit()
        raise AuthError(GENERIC_LOGIN_ERROR)

    return user


# LOGIN LANGKAH 2: OTP
def can_continue_login(user):
    # Bisa lanjut ke OTP alau akun aktif + ga dikunci.
    return user.is_active and not is_account_locked(user)

def ensure_can_continue_login(user):
    # Dicek ulang di langkah OTP, bisa aja aunnya dikunci/dinonatifkan setelah lolos password
    if not user.is_active:
        raise AuthError(INACTIVE_ACCOUNT_ERROR)
    if is_account_locked(user):
        raise AuthError(ACCOUNT_LOCKED_ERROR)

def get_latest_otp(user_id, is_unused_only=False):
    """Ambil OTP paling baru milik user (opsional: yg belum kepake aja)."""
    query = db.select(OtpCode).filter_by(user_id=user_id)
    if is_unused_only:
        query = query.filter_by(is_used=False)
    return db.session.execute(query.order_by(OtpCode.id.desc()).limit(1)).scalar_one_or_none()


def start_otp_challenge(user):
    """Bikin OTP baru, hangusin OTP lama, terus kirim ke user."""
    # OTP lama yg belum kepake dihangusin, biar cuma ada 1 OTP aktif
    db.session.execute(
        db.update(OtpCode)
        .where(OtpCode.user_id == user.id, OtpCode.is_used.is_(False))
        .values(is_used=True)
    )

    otp_code = generate_otp_code()
    db.session.add(OtpCode(
        user_id=user.id,
        code_hash=hash_otp_code(otp_code),
        expires_at=utc_now() + timedelta(minutes=OTP_EXPIRE_MINUTES),
    ))
    db.session.commit()

    # kirim setelah kesimpen, jadi OTP yg dikirim pasti valid
    send_otp_code(user, otp_code)


def resend_otp_challenge(user):
    """Kirim ulang OTP, tapi harus nunggu jeda dulu biar ga di-spam."""
    ensure_can_continue_login(user)
    latest_otp = get_latest_otp(user.id)
    if latest_otp is not None:
        next_allowed_at = to_utc_aware(latest_otp.created_at) + timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS)
        if next_allowed_at > utc_now():
            raise AuthError("Tunggu sebentar sebelum minta OTP baru")
    start_otp_challenge(user)


def verify_otp_code(user, otp_code):
    """Cek OTP. Kalau bener, OTP ditandai kepake & login dicatat. Kalau salah, lempar AuthError."""
    ensure_can_continue_login(user)
    active_otp = get_latest_otp(user.id, is_unused_only=True)

    # ga ada OTP aktif atau udah lewat waktunya
    if active_otp is None or to_utc_aware(active_otp.expires_at) < utc_now():
        raise AuthError("OTP sudah kedaluwarsa, silakan minta OTP baru")

    # OTP salah: dihitung per OTP & ikut nambah hitungan gagal akun,
    # biar ga bisa nebak OTP terus-terusan cuma modal minta OTP baru
    if not is_otp_code_match(otp_code, active_otp.code_hash):
        active_otp.attempt_count += 1
        register_failed_login(user)
        is_locked = is_account_locked(user)
        is_attempt_exhausted = active_otp.attempt_count >= OTP_MAX_ATTEMPT_COUNT
        if is_attempt_exhausted or is_locked:
            # kebanyakan salah -> OTP hangus
            active_otp.is_used = True
        log_audit(AUDIT_ACTION_LOGIN_FAILED, "users", entity_id=user.id, user=user, new_data_dict={"reason": "wrong_otp"})
        db.session.commit()
        if is_locked:
            raise AuthError(ACCOUNT_LOCKED_ERROR)
        if is_attempt_exhausted:
            raise AuthError("Terlalu banyak percobaan OTP, silakan minta OTP baru")
        raise AuthError("Kode OTP salah")

    # OTP benar -> tandai kepake, reset hitungan gagal, catat login
    active_otp.is_used = True
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = utc_now()
    log_audit(AUDIT_ACTION_LOGIN, "users", entity_id=user.id, user=user)
    db.session.commit()
    return user