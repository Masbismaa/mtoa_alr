"""Logika akun (dibikin admin + aktivasi lewat link email), login (password), OTP, dan lupa password.
Route tinggal manggil fungsi di sini.

Aturan yg dipegang di file ini:
- layar login & lupa password ga pernah ngasih tau email mana yg udah terdaftar (pesan & alurnya sama)
- salah password / OTP (digabung) LOGIN_MAX_FAILED_COUNT kali -> akun dikunci 15 menit (status Locked, bisa di-unlock
  admin) + email-nya diblokir di security/auth_throttle.py biar email ga terdaftar dapet pesan yg sama
"""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import hashlib
import secrets
import smtplib

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import OtpCode, User, UserPreference
from app.security import auth_throttle
from app.security.otp_service import generate_otp_code, hash_otp_code, is_otp_code_match
from app.security.password_service import hash_password, is_rehash_needed, verify_password
from app.services.audit_service import log_audit
from app.services.notification_service import send_otp_code, send_password_changed_notice
from app.services.user_notification_service import add_notification
from app.utils.constants import (
    ACTIVATION_LINK_EXPIRE_HOURS,
    AUDIT_ACTION_CREATE,
    AUDIT_ACTION_LOGIN,
    AUDIT_ACTION_LOGIN_FAILED,
    AUDIT_ACTION_PASSWORD_CHANGE,
    AUDIT_ACTION_UPDATE,
    LOGIN_LOCK_MINUTES,
    LOGIN_MAX_FAILED_COUNT,
    OTP_EXPIRE_MINUTES,
    OTP_MAX_ATTEMPT_COUNT,
    OTP_PURPOSE_ACTIVATION,
    OTP_PURPOSE_LOGIN,
    OTP_PURPOSE_RESET,
    OTP_RESEND_COOLDOWN_SECONDS,
    ROLE_LIST,
    ROLE_USER_ENTRY,
    UNUSABLE_PASSWORD_HASH,
)
from app.utils.datetime_helper import to_utc_aware, utc_now
from app.utils.exceptions import AuthError
from app.utils.request_helper import get_client_ip
from app.utils.sanitizer import sanitize_text
from app.utils.text_helper import normalize_email

# pesan login gagal dibikin sama semua, biar orang ga bisa nebak email mana yg terdaftar
GENERIC_LOGIN_ERROR = "Incorrect email or password"
ACCOUNT_LOCKED_ERROR = f"The account is temporarily locked after too many attempts. Try again in {LOGIN_LOCK_MINUTES} minutes."
INACTIVE_ACCOUNT_ERROR = "This account is inactive; contact an admin to reactivate it."
# pesan OTP dipake bareng login & lupa password (cabang email ga terdaftar wajib pake pesan yg sama persis)
OTP_EXPIRED_ERROR = "The OTP has expired, please request a new one"
OTP_EXHAUSTED_ERROR = "Too many OTP attempts, please request a new one"
OTP_WRONG_ERROR = "Incorrect OTP code"
OTP_COOLDOWN_ERROR = "Wait a moment before requesting a new OTP"
ACTIVATION_LINK_INVALID_ERROR = "This activation link is invalid or has expired. Ask the ICT admin to send a new one."

def build_login_blocked_error(minute_count):
    return f"Too many login attempts. Try again in {minute_count} minutes or contact the ICT admin."


# AKUN BARU
#
# Ga ada halaman daftar. Admin bikin akun (email + nama + role) -> status Pending Activation (belum aktif, belum punya
# password) -> admin klik Send Activation Link -> pemilik email buka link, bikin password -> akun aktif -> login biasa.
# Token link disimpen di otp_codes (purpose=activation) dalam bentuk sha256, token aslinya cuma ada di email.

def is_allowed_email_domain(email):
    """Cek email pake domain yg diizinin (default @spindo.com)."""
    allowed_domain = current_app.config["ALLOWED_EMAIL_DOMAIN"].lower()
    return email.count("@") == 1 and email.endswith(f"@{allowed_domain}")


def ensure_allowed_email_domain(clean_email):
    if not is_allowed_email_domain(clean_email):
        raise AuthError(f"Email must use the @{current_app.config['ALLOWED_EMAIL_DOMAIN']} domain")


def build_user_audit_dict(user):
    """Data user yg dicatat ke audit log (tanpa password)."""
    return {
        "email": user.email,
        "full_name": user.full_name,
        "department": user.department,
        "job_title": user.job_title,
        "role": user.role,
    }


def clean_profile(full_name, department, job_title):
    """Data profil dibersihin dari tag HTML dkk & wajib keisi semua. Dipake create-admin & edit profil di Settings."""
    profile_dict = {
        "full_name": sanitize_text(full_name, max_length=150),
        "department": sanitize_text(department, max_length=100),
        "job_title": sanitize_text(job_title, max_length=100),
    }
    if not all(profile_dict.values()):
        raise AuthError("Name, department, and job title are required")
    return profile_dict


def update_profile(user, full_name, department, job_title):
    """Edit profil sendiri (email & role ga bisa diubah dari sini). Dicatat ke audit log kalau ada yg berubah."""
    profile_dict = clean_profile(full_name, department, job_title)
    old_data_dict = build_user_audit_dict(user)
    for key, value in profile_dict.items():
        setattr(user, key, value)
    new_data_dict = build_user_audit_dict(user)
    if new_data_dict != old_data_dict:
        log_audit(AUDIT_ACTION_UPDATE, "users", entity_id=user.id, old_data_dict=old_data_dict,
                  new_data_dict=new_data_dict, user=user)
    db.session.commit()
    return user


def find_user_by_email(clean_email):
    return db.session.execute(db.select(User).filter_by(email=clean_email)).scalar_one_or_none()


def create_user_account(clean_email, profile_dict, role, actor=None):
    """Bikin akun + preferensi tampilan default, dicatat ke audit log (actor None = akunnya sendiri). Commit di pemanggil."""
    user = User(email=clean_email, role=role, **profile_dict)
    user.preference = UserPreference()
    db.session.add(user)
    # flush biar user.id udah keisi buat dicatat ke audit
    db.session.flush()
    log_audit(AUDIT_ACTION_CREATE, "users", entity_id=user.id, new_data_dict=build_user_audit_dict(user), user=actor or user)
    return user


def register_user(email, password, full_name, department, job_title, role=ROLE_USER_ENTRY):
    """Bikin akun yg LANGSUNG aktif tanpa aktivasi. Cuma dipake perintah CLI create-admin dan data test."""
    clean_email = normalize_email(email)
    ensure_allowed_email_domain(clean_email)
    profile_dict = clean_profile(full_name, department, job_title)
    profile_dict["password_hash"] = hash_new_password(password)
    if find_user_by_email(clean_email) is not None:
        raise AuthError("Email is already registered")
    user = create_user_account(clean_email, profile_dict, role)
    db.session.commit()
    return user


def create_pending_user(actor, email, full_name, role):
    """Admin bikin akun baru: belum aktif & belum punya password sampai pemiliknya aktivasi lewat link email.
    Departemen & jabatan dikosongin, diisi sendiri nanti di Settings."""
    clean_email = normalize_email(email)
    ensure_allowed_email_domain(clean_email)
    clean_full_name = sanitize_text(full_name, max_length=150)
    if not clean_full_name:
        raise AuthError("Name is required")
    if role not in ROLE_LIST:
        raise AuthError("Invalid role")
    if find_user_by_email(clean_email) is not None:
        raise AuthError("Email is already registered")
    profile_dict = {
        "full_name": clean_full_name, "department": "", "job_title": "",
        "password_hash": UNUSABLE_PASSWORD_HASH, "is_active": False,
    }
    try:
        user = create_user_account(clean_email, profile_dict, role, actor=actor)
        db.session.commit()
    except IntegrityError:
        # 2 admin bikin email yg sama di detik yg sama
        db.session.rollback()
        raise AuthError("Email is already registered") from None
    return user


def is_pending_activation(user):
    """Akun dari admin yg pemiliknya belum bikin password lewat link aktivasi."""
    return user.deleted_at is None and user.password_hash == UNUSABLE_PASSWORD_HASH


def hash_activation_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_activation_token(user):
    """Token link aktivasi baru (link lama langsung ga berlaku). Return (token asli buat link email, baris OtpCode)."""
    user = lock_auth_user(user)
    db.session.execute(
        db.update(OtpCode)
        .where(OtpCode.user_id == user.id, OtpCode.purpose == OTP_PURPOSE_ACTIVATION, OtpCode.is_used.is_(False))
        .values(is_used=True)
    )
    token = secrets.token_urlsafe(32)
    activation = OtpCode(
        user_id=user.id, code_hash=hash_activation_token(token), purpose=OTP_PURPOSE_ACTIVATION,
        expires_at=utc_now() + timedelta(hours=ACTIVATION_LINK_EXPIRE_HOURS),
    )
    db.session.add(activation)
    db.session.commit()
    return token, activation


def get_activation(token, is_lock=False):
    """Token aktivasi yg masih berlaku + akunnya masih Pending. None kalau link salah / kepake / kedaluwarsa."""
    if not token:
        return None
    query = db.select(OtpCode).where(
        OtpCode.code_hash == hash_activation_token(token),
        OtpCode.purpose == OTP_PURPOSE_ACTIVATION,
        OtpCode.is_used.is_(False),
    )
    if is_lock:
        query = query.with_for_update()
    activation = db.session.execute(query).scalar_one_or_none()
    if activation is None or to_utc_aware(activation.expires_at) < utc_now():
        return None
    user = db.session.get(User, activation.user_id)
    return activation if user is not None and is_pending_activation(user) else None


def activate_account(token, new_password):
    """Pemilik email bikin password dari link aktivasi -> akun aktif. Return User. Login-nya tetep lewat password + OTP."""
    password_hash = hash_new_password(new_password)
    activation = get_activation(token, is_lock=True)
    if activation is None:
        raise AuthError(ACTIVATION_LINK_INVALID_ERROR)
    user = lock_auth_user(db.session.get(User, activation.user_id))
    user.is_active = True
    # token aktivasi ikut hangus di apply_new_password (semua kode aktif user ini)
    apply_new_password(user, password_hash, "activation")
    db.session.commit()
    return user


def check_code_without_account(state):
    """Lupa password buat email tanpa akun aktif: ga ada kode yg bener, tapi pesan, batas percobaan, & kedaluwarsanya
    dibikin sama persis kayak kode asli. Selalu lempar AuthError; hitungannya disimpen di state (session)."""
    sent_at = datetime.fromtimestamp(state["sent_at"], tz=timezone.utc)
    if state["attempt_count"] >= OTP_MAX_ATTEMPT_COUNT or sent_at + timedelta(minutes=OTP_EXPIRE_MINUTES) < utc_now():
        raise AuthError(OTP_EXPIRED_ERROR)
    state["attempt_count"] += 1
    if state["attempt_count"] >= OTP_MAX_ATTEMPT_COUNT:
        raise AuthError(OTP_EXHAUSTED_ERROR)
    raise AuthError(OTP_WRONG_ERROR)


# LOGIN LANGKAH 1: EMAIL + PASSWORD

@lru_cache(maxsize=1)
def get_dummy_password_hash():
    """Hash palsu buat email yg ga terdaftar, biar waktu responnya sama kayak email asli."""
    return hash_password("dummy-password-cuma-buat-timing-123")


def is_account_locked(user):
    """True kalau akun lagi dikunci (gara-gara kebanyakan salah password/OTP)."""
    return user.locked_until is not None and to_utc_aware(user.locked_until) > utc_now()


def register_failed_attempt(user):
    """Tambah hitungan salah password/OTP (digabung). Kalau nyampe batas, kunci akunnya (status Locked)."""
    user.failed_login_count += 1
    if user.failed_login_count >= LOGIN_MAX_FAILED_COUNT:
        user.locked_until = utc_now() + timedelta(minutes=LOGIN_LOCK_MINUTES)
        # hitungan di-reset, nanti mulai dari 0 lagi pas kunci udah kebuka
        user.failed_login_count = 0


def notify_login_blocked(user, ip_address):
    """Kabarin pemilik akun lewat lonceng: ada yg salah password berkali-kali dari IP tertentu."""
    add_notification(
        user.id,
        f"There were {LOGIN_MAX_FAILED_COUNT} failed login attempts on your account from IP {ip_address}. "
        "If that wasn't you, contact the ICT admin.",
    )


def authenticate_user(email, password):
    """Cek email + password. Return User kalau bener, lempar AuthError kalau salah.

    Urutannya penting biar ga bocor:
    1. email lagi diblokir -> tolak (pesannya sama buat email terdaftar maupun ngga)
    2. email ga ada / nonaktif / password salah -> pesan generik + catat gagal per email (+ hitungan kunci akun)
    3. akun lagi dikunci -> pesan "dikunci" cuma keluar kalau password-nya bener
    """
    clean_email = normalize_email(email)
    ip_address = get_client_ip() or "-"
    blocked_minute_count = auth_throttle.get_login_block_minutes(clean_email)
    if blocked_minute_count:
        log_audit(AUDIT_ACTION_LOGIN_FAILED, "users", actor_email=clean_email[:255],
                  new_data_dict={"reason": "too_many_attempts"}, is_commit=True)
        raise AuthError(build_login_blocked_error(blocked_minute_count))

    user = db.session.execute(
        db.select(User).filter_by(email=clean_email).with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()

    # email ga terdaftar: tetep jalanin verifikasi palsu biar waktunya sama
    if user is None:
        verify_password(get_dummy_password_hash(), password or "")
        auth_throttle.record_login_failure(clean_email)
        log_audit(AUDIT_ACTION_LOGIN_FAILED, "users", actor_email=clean_email[:255], is_commit=True)
        raise AuthError(GENERIC_LOGIN_ERROR)

    # akun nonaktif atau password salah -> pesannya tetep sama
    if not user.is_active or not verify_password(user.password_hash, password):
        is_newly_blocked = auth_throttle.record_login_failure(clean_email)
        if user.is_active:
            register_failed_attempt(user)
        if is_newly_blocked and user.is_active:
            notify_login_blocked(user, ip_address)
        failed_reason = "inactive" if not user.is_active else "wrong_password"
        log_audit(AUDIT_ACTION_LOGIN_FAILED, "users", entity_id=user.id, user=user, new_data_dict={"reason": failed_reason})
        db.session.commit()
        raise AuthError(GENERIC_LOGIN_ERROR)

    # password bener tapi akun lagi dikunci (salah OTP)
    if is_account_locked(user):
        log_audit(
            AUDIT_ACTION_LOGIN_FAILED, "users", entity_id=user.id, user=user,
            new_data_dict={"reason": "account_locked"}, is_commit=True,
        )
        raise AuthError(ACCOUNT_LOCKED_ERROR)

    auth_throttle.clear_login_failure(clean_email)
    # hash lama (parameter argon2 udah dinaikin) langsung diganti hash baru, kesimpen pas OTP dibikin
    if is_rehash_needed(user.password_hash):
        user.password_hash = hash_password(password)
    return user


# LOGIN LANGKAH 2: OTP
def can_continue_login(user):
    # bisa lanjut ke OTP kalau akun aktif + ga dikunci
    return user.is_active and not is_account_locked(user)

def ensure_can_continue_login(user):
    # dicek ulang di langkah OTP, bisa aja akunnya dikunci/dinonaktifkan setelah lolos password
    if not user.is_active:
        raise AuthError(INACTIVE_ACCOUNT_ERROR)
    if is_account_locked(user):
        raise AuthError(ACCOUNT_LOCKED_ERROR)

def get_latest_otp(user_id, is_unused_only=False, purpose=OTP_PURPOSE_LOGIN):
    """Ambil OTP paling baru milik user buat keperluan itu (login / reset), opsional yg belum kepake aja."""
    query = db.select(OtpCode).filter_by(user_id=user_id, purpose=purpose)
    if is_unused_only:
        query = query.filter_by(is_used=False)
    return db.session.execute(query.order_by(OtpCode.id.desc()).limit(1)).scalar_one_or_none()


def is_otp_cooldown_active(user_id, purpose=OTP_PURPOSE_LOGIN):
    """True kalau OTP terakhir baru aja dikirim (belum lewat jeda kirim ulang)."""
    latest_otp = get_latest_otp(user_id, purpose=purpose)
    if latest_otp is None:
        return False
    return to_utc_aware(latest_otp.created_at) + timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS) > utc_now()


def lock_auth_user(user):
    """Serialisasi password/OTP per akun di PostgreSQL, termasuk request bersamaan."""
    return db.session.execute(
        db.select(User).where(User.id == user.id).with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()


def start_otp_challenge(user):
    """Bikin OTP login baru, hangusin OTP lama, terus kirim ke user."""
    user = lock_auth_user(user)
    ensure_can_continue_login(user)
    # OTP lama yg belum kepake dihangusin, biar cuma ada 1 OTP aktif
    db.session.execute(
        db.update(OtpCode)
        .where(OtpCode.user_id == user.id, OtpCode.purpose == OTP_PURPOSE_LOGIN, OtpCode.is_used.is_(False))
        .values(is_used=True)
    )

    otp_code = generate_otp_code()
    challenge = OtpCode(
        user_id=user.id,
        code_hash=hash_otp_code(otp_code),
        expires_at=utc_now() + timedelta(minutes=OTP_EXPIRE_MINUTES),
    )
    db.session.add(challenge)
    db.session.commit()

    # kirim setelah kesimpen, jadi OTP yg dikirim pasti valid
    try:
        send_otp_code(user, otp_code)
    except (OSError, smtplib.SMTPException, RuntimeError, ValueError):
        challenge.is_used = True
        db.session.commit()
        current_app.logger.error("Pengiriman OTP gagal; periksa layanan SMTP")
        raise AuthError("The OTP could not be sent. Try again or contact an admin.") from None


def resend_otp_challenge(user):
    """Kirim ulang OTP, tapi harus nunggu jeda dulu biar ga di-spam."""
    user = lock_auth_user(user)
    ensure_can_continue_login(user)
    if is_otp_cooldown_active(user.id):
        raise AuthError(OTP_COOLDOWN_ERROR)
    start_otp_challenge(user)


def verify_otp_code(user, otp_code):
    """Cek OTP. Kalau bener, OTP ditandai kepake & login dicatat. Kalau salah, lempar AuthError."""
    user = lock_auth_user(user)
    ensure_can_continue_login(user)
    active_otp = get_latest_otp(user.id, is_unused_only=True)

    # ga ada OTP aktif atau udah lewat waktunya
    if active_otp is None or to_utc_aware(active_otp.expires_at) < utc_now():
        raise AuthError(OTP_EXPIRED_ERROR)

    # OTP salah: dihitung per OTP & ikut nambah hitungan gagal akun,
    # biar ga bisa nebak OTP terus-terusan cuma modal minta OTP baru
    if not is_otp_code_match(otp_code, active_otp.code_hash):
        active_otp.attempt_count += 1
        register_failed_attempt(user)
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
            raise AuthError(OTP_EXHAUSTED_ERROR)
        raise AuthError(OTP_WRONG_ERROR)

    # OTP benar -> tandai kepake, reset hitungan gagal, catat login
    active_otp.is_used = True
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = utc_now()
    log_audit(AUDIT_ACTION_LOGIN, "users", entity_id=user.id, user=user)
    db.session.commit()
    return user


# LUPA PASSWORD & GANTI PASSWORD
#
# Layar lupa password SELALU sama ("kalau terdaftar, kode udah dikirim"), state di session,
# email yg ga punya akun aktif ngelewatin alur palsu yg pesannya sama persis. Kode reset disimpen di otp_codes
# (purpose=reset), kepisah dari OTP login. Salah kode reset sengaja ga ngunci akun: kalau ngunci, orang iseng tinggal
# minta reset ke email orang lain terus salahin kodenya. Tebakan udah kebatas per kode (OTP_MAX_ATTEMPT_COUNT) & per email.

RESET_BLOCKED_ERROR = "Too many reset attempts from this device. Try again tomorrow or contact the ICT admin."
PASSWORD_CHANGED_NOTIFICATION = "Your password was changed. If this wasn't you, contact the ICT admin right away."


def build_password_reset_state(clean_email):
    return {"email": clean_email, "sent_at": utc_now().timestamp(), "attempt_count": 0}


def find_resettable_user(clean_email):
    """Akun yg boleh reset password: ada & aktif (akun nonaktif/dihapus diperlakuin kayak email ga terdaftar)."""
    user = find_user_by_email(clean_email)
    return user if user is not None and user.is_active else None


def issue_password_reset_code(user):
    """Kode reset baru (yg lama hangus), simpen, baru kirim. Lewat batas per email / SMTP mati: diem aja
    (cuma dicatat di log), soalnya kalau nongol di layar ketauan email ini terdaftar."""
    if not auth_throttle.allow_reset_code(user.email):
        return
    # dikunci kayak verifikasi: 2 permintaan barengan ga bisa sama-sama ninggalin kode aktif
    user = lock_auth_user(user)
    db.session.execute(
        db.update(OtpCode)
        .where(OtpCode.user_id == user.id, OtpCode.purpose == OTP_PURPOSE_RESET, OtpCode.is_used.is_(False))
        .values(is_used=True)
    )
    code = generate_otp_code()
    db.session.add(OtpCode(
        user_id=user.id, code_hash=hash_otp_code(code), purpose=OTP_PURPOSE_RESET,
        expires_at=utc_now() + timedelta(minutes=OTP_EXPIRE_MINUTES),
    ))
    db.session.commit()
    try:
        send_otp_code(user, code, OTP_PURPOSE_RESET)
    except (OSError, smtplib.SMTPException, RuntimeError, ValueError):
        current_app.logger.error("Pengiriman kode lupa password gagal; periksa layanan SMTP")


def start_password_reset(email):
    """Minta kode lupa password. Return state buat session. Hasil di layar sama, terdaftar atau nggak.
    ponytail: lama kirim email (SMTP) masih bisa beda dikit antara email terdaftar & nggak; kalau perlu ditutup,
    kirim emailnya lewat antrean/worker biar respon langsung balik."""
    clean_email = normalize_email(email)
    ensure_allowed_email_domain(clean_email)
    user = find_resettable_user(clean_email)
    if user is not None:
        issue_password_reset_code(user)
    return build_password_reset_state(clean_email)


def resend_password_reset_code(state):
    """Kirim ulang kode reset (jeda 60 dtk, sama kayak OTP lain). state di-reset kayak kode baru."""
    sent_at = datetime.fromtimestamp(state["sent_at"], tz=timezone.utc)
    if sent_at + timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS) > utc_now():
        raise AuthError(OTP_COOLDOWN_ERROR)
    user = find_resettable_user(state["email"])
    if user is not None:
        if is_otp_cooldown_active(user.id, OTP_PURPOSE_RESET):
            raise AuthError(OTP_COOLDOWN_ERROR)
        issue_password_reset_code(user)
    state["sent_at"] = utc_now().timestamp()
    state["attempt_count"] = 0


def apply_new_password(user, password_hash, method):
    """Simpen password baru + logout semua sesi lama (session_version naik, login yg lagi nunggu OTP ikut batal)
    + semua OTP aktif (login & reset) hangus + catat audit. Dipake reset & ganti password. Commit di pemanggil."""
    db.session.execute(
        db.update(OtpCode).where(OtpCode.user_id == user.id, OtpCode.is_used.is_(False)).values(is_used=True)
    )
    user.password_hash = password_hash
    user.session_version += 1
    log_audit(AUDIT_ACTION_PASSWORD_CHANGE, "users", entity_id=user.id, user=user, new_data_dict={"method": method})


def notify_password_changed(user):
    """Kabarin pemilik akun lewat lonceng + email. Email gagal cuma dicatat, password-nya udah keganti."""
    add_notification(user.id, PASSWORD_CHANGED_NOTIFICATION)
    db.session.commit()
    try:
        send_password_changed_notice(user)
    except (OSError, smtplib.SMTPException, RuntimeError, ValueError):
        current_app.logger.error("Pengiriman email pemberitahuan ganti password gagal; periksa layanan SMTP")


def hash_new_password(new_password):
    try:
        return hash_password(new_password)
    except ValueError as error:
        raise AuthError(str(error)) from error


def reset_password(state, code, new_password):
    """Cek kode reset; bener -> password diganti, semua sesi & OTP lama hangus, kunci akun dibuka. Return User."""
    password_hash = hash_new_password(new_password)
    # dihitung buat SEMUA email (terdaftar atau nggak), biar pesannya ga bocorin email mana yg terdaftar
    if not auth_throttle.allow_reset_attempt(state["email"], get_client_ip() or "-"):
        raise AuthError(RESET_BLOCKED_ERROR)
    user = find_resettable_user(state["email"])
    if user is None:
        check_code_without_account(state)
    user = lock_auth_user(user)
    reset_otp = get_latest_otp(user.id, is_unused_only=True, purpose=OTP_PURPOSE_RESET)
    if reset_otp is None or to_utc_aware(reset_otp.expires_at) < utc_now():
        raise AuthError(OTP_EXPIRED_ERROR)
    if not is_otp_code_match(code, reset_otp.code_hash):
        reset_otp.attempt_count += 1
        is_attempt_exhausted = reset_otp.attempt_count >= OTP_MAX_ATTEMPT_COUNT
        reset_otp.is_used = is_attempt_exhausted
        db.session.commit()
        raise AuthError(OTP_EXHAUSTED_ERROR if is_attempt_exhausted else OTP_WRONG_ERROR)

    # kode bener = pemilik email (OTP lain ikut hangus di apply_new_password)
    user.failed_login_count = 0
    user.locked_until = None
    apply_new_password(user, password_hash, "reset")
    db.session.commit()
    auth_throttle.clear_login_failure(user.email)
    notify_password_changed(user)
    return user


def change_password(user, current_password, new_password):
    """Ganti password dari Settings. Password lama salah ikut hitungan blokir login & kunci akun, biar sesi yg kebajak
    ga bisa dipake nebak password. Return User (session_version-nya udah naik, route login-in ulang sesi ini)."""
    blocked_minute_count = auth_throttle.get_login_block_minutes(user.email)
    if blocked_minute_count:
        raise AuthError(build_login_blocked_error(blocked_minute_count))
    user = lock_auth_user(user)
    if not verify_password(user.password_hash, current_password or ""):
        auth_throttle.record_login_failure(user.email)
        register_failed_attempt(user)
        db.session.commit()
        raise AuthError("Current password is incorrect")
    if verify_password(user.password_hash, new_password or ""):
        db.session.commit()
        raise AuthError("The new password must be different from the current one")
    apply_new_password(user, hash_new_password(new_password), "settings")
    db.session.commit()
    notify_password_changed(user)
    return user
