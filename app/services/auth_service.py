"""Logika register (dgn verifikasi email), login (password), dan OTP. Route tinggal manggil fungsi di sini.

Dua aturan anti bocor yg dipegang di file ini:
- layar ga pernah ngasih tau email mana yg udah terdaftar (login: pesan sama; daftar: alur & tampilan sama persis)
- orang lain ga bisa ngunci akun kita: salah password diblokir per email+IP (security/auth_throttle.py),
  akunnya sendiri cuma dikunci kalau salah OTP (yg bisa sampe OTP pasti udah tau password)
"""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import hashlib
import secrets
import smtplib

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import OtpCode, PendingRegistration, User, UserPreference
from app.security import auth_throttle
from app.security.otp_service import generate_otp_code, hash_otp_code, is_otp_code_match
from app.security.password_service import hash_password, is_rehash_needed, verify_password
from app.services.audit_service import log_audit
from app.services.notification_service import send_otp_code, send_registration_notice
from app.services.user_notification_service import add_notification
from app.utils.constants import (
    AUDIT_ACTION_CREATE,
    AUDIT_ACTION_LOGIN,
    AUDIT_ACTION_LOGIN_FAILED,
    LOGIN_LOCK_MINUTES,
    LOGIN_MAX_FAILED_COUNT,
    OTP_EXPIRE_MINUTES,
    OTP_MAX_ATTEMPT_COUNT,
    OTP_PURPOSE_REGISTER,
    PENDING_REGISTRATION_EXPIRE_HOURS,
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
# pesan OTP dipake bareng login & verifikasi daftar (cabang "email udah terdaftar" wajib pake pesan yg sama persis)
OTP_EXPIRED_ERROR = "OTP sudah kedaluwarsa, silakan minta OTP baru"
OTP_EXHAUSTED_ERROR = "Terlalu banyak percobaan OTP, silakan minta OTP baru"
OTP_WRONG_ERROR = "Kode OTP salah"
OTP_COOLDOWN_ERROR = "Tunggu sebentar sebelum minta OTP baru"
REGISTRATION_FINISHED_ERROR = "Pendaftaran untuk email ini sudah selesai. Silakan login."

def build_login_blocked_error(minute_count):
    return f"Terlalu banyak percobaan login dari perangkat ini. Coba lagi dalam {minute_count} menit."


# REGISTER
#
# Alur daftar (halaman publik):
#   start_registration  -> percobaan daftar disimpen di pending_registrations + token di session pendaftar + kode ke email
#   verify_registration -> kode bener -> BARU bikin akun di users
# Email yg udah punya akun ngelewatin alur yg kerasa sama persis di layar (tanpa baris DB), pemiliknya cuma dapet email
# pemberitahuan. Tabel users dijamin cuma berisi akun yg emailnya udah kebukti.

class RegistrationFinishedError(AuthError):
    """Kode bener, tapi email ini keburu jadi akun lewat percobaan lain. Route ngarahin ke login.
    Aman ditampilin: cuma bisa nyampe sini kalau pegang kode yg dikirim ke email itu."""


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


def prepare_registration(email, password, full_name, department, job_title):
    """Validasi isian daftar + hash password. Return (email bersih, dict profil + password_hash).
    Sengaja ga ngecek email udah kepake atau belum di sini: pesan validasi ga boleh bocorin itu."""
    clean_email = normalize_email(email)

    # cuma email kantor yg boleh daftar
    if not is_allowed_email_domain(clean_email):
        raise AuthError(f"Email wajib pakai domain @{current_app.config['ALLOWED_EMAIL_DOMAIN']}")

    # bersihin data profil dari tag HTML dkk
    profile_dict = {
        "full_name": sanitize_text(full_name, max_length=150),
        "department": sanitize_text(department, max_length=100),
        "job_title": sanitize_text(job_title, max_length=100),
    }
    if not all(profile_dict.values()):
        raise AuthError("Nama, departemen, dan jabatan wajib diisi")

    # hash password (sekalian dicek panjang minimalnya). Selalu dijalanin, termasuk buat email yg udah terdaftar,
    # biar lama respon daftar sama aja
    try:
        profile_dict["password_hash"] = hash_password(password)
    except ValueError as error:
        raise AuthError(str(error)) from error
    return clean_email, profile_dict


def find_user_by_email(clean_email):
    return db.session.execute(db.select(User).filter_by(email=clean_email)).scalar_one_or_none()


def create_user_account(clean_email, profile_dict, role):
    """Bikin akun + preferensi tampilan default, dicatat ke audit log. Commit-nya di pemanggil."""
    user = User(email=clean_email, role=role, **profile_dict)
    user.preference = UserPreference()
    db.session.add(user)
    # flush biar user.id udah keisi buat dicatat ke audit
    db.session.flush()
    log_audit(AUDIT_ACTION_CREATE, "users", entity_id=user.id, new_data_dict=build_user_audit_dict(user), user=user)
    return user


def register_user(email, password, full_name, department, job_title, role=ROLE_USER_ENTRY):
    """Bikin akun yg LANGSUNG aktif, tanpa verifikasi email.

    Dipake perintah CLI create-admin (role admin cuma bisa lewat situ) dan data test.
    Halaman register publik pake start_registration (wajib verifikasi email dulu).
    """
    clean_email, profile_dict = prepare_registration(email, password, full_name, department, job_title)
    if find_user_by_email(clean_email) is not None:
        raise AuthError("Email sudah terdaftar")
    user = create_user_account(clean_email, profile_dict, role)
    db.session.commit()
    return user


def hash_registration_token(token):
    """Token percobaan daftar disimpen di DB dalam bentuk hash (yg asli cuma ada di session pendaftar)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def build_registration_state(clean_email, token):
    """Data pendaftaran yg disimpen di session sampai kode verifikasi dimasukin.
    sent_at & attempt_count cuma kepake buat cabang "email udah terdaftar" (biar perilakunya sama kayak kode asli)."""
    return {"email": clean_email, "token": token, "sent_at": utc_now().timestamp(), "attempt_count": 0}


def delete_expired_pending_registration():
    """Buang percobaan daftar yg udah lewat 24 jam (dipanggil tiap ada yg daftar, biar tabelnya ga numpuk)."""
    expired_before = utc_now() - timedelta(hours=PENDING_REGISTRATION_EXPIRE_HOURS)
    db.session.execute(db.delete(PendingRegistration).where(PendingRegistration.created_at < expired_before))


def issue_registration_code(pending):
    """Bikin kode baru buat percobaan daftar ini (kode lama otomatis ga berlaku), simpen, baru kirim ke email.

    Gagal kirim (SMTP mati) cuma dicatat di log, ga nongol di layar: cabang "email udah terdaftar" juga diem kalau
    gagal, jadi tampilannya tetep sama (ga bocor). User tinggal klik Kirim ulang nanti.
    Kode daftar per email dibatasi (anti spam kotak masuk orang); lewat batas = ga dikirim, layar tetep sama."""
    code = generate_otp_code()
    now = utc_now()
    pending.code_hash = hash_otp_code(code)
    pending.code_expires_at = now + timedelta(minutes=OTP_EXPIRE_MINUTES)
    pending.attempt_count = 0
    pending.last_sent_at = now
    db.session.add(pending)
    db.session.commit()
    if not auth_throttle.allow_register_code(pending.email):
        return
    try:
        send_otp_code(pending, code, OTP_PURPOSE_REGISTER)
    except (OSError, smtplib.SMTPException, RuntimeError, ValueError):
        current_app.logger.error("Pengiriman kode verifikasi pendaftaran gagal; periksa layanan SMTP")


def start_registration(email, password, full_name, department, job_title):
    """Daftar lewat halaman register. Return data buat session (build_registration_state).

    Hasil di layar SELALU sama ("kode dikirim ke email kamu"), apa pun kondisi emailnya:
    - email belum punya akun -> percobaan baru disimpen + kode dikirim. Percobaan lain buat email yg sama
                                (punya orang lain) ga diubah sama sekali.
    - email udah punya akun  -> akun ga diubah; pemiliknya dapet email pemberitahuan
    """
    clean_email, profile_dict = prepare_registration(email, password, full_name, department, job_title)
    token = secrets.token_urlsafe(32)
    delete_expired_pending_registration()
    user = find_user_by_email(clean_email)
    if user is not None:
        db.session.commit()
        send_registration_notice_safely(user)
        return build_registration_state(clean_email, token)

    issue_registration_code(PendingRegistration(email=clean_email, token_hash=hash_registration_token(token), **profile_dict))
    return build_registration_state(clean_email, token)


def send_registration_notice_safely(user):
    """Email pemberitahuan ke pemilik akun, maksimal sekali per 10 menit. Gagal kirim cuma dicatat di log:
    kalau error-nya nongol di layar, ketauan email ini udah terdaftar."""
    if not auth_throttle.allow_register_notice(user.email):
        return
    try:
        send_registration_notice(user)
    except (OSError, smtplib.SMTPException, RuntimeError, ValueError):
        current_app.logger.error("Pengiriman email pemberitahuan pendaftaran gagal; periksa layanan SMTP")


def get_pending_registration(state):
    """Percobaan daftar milik session ini (dikunci barisnya biar verifikasi bareng-bareng ga dobel). None kalau ga ada."""
    return db.session.execute(
        db.select(PendingRegistration)
        .where(PendingRegistration.token_hash == hash_registration_token(state["token"]),
               PendingRegistration.email == state["email"])
        .with_for_update()
    ).scalar_one_or_none()


def check_registration_without_account(state):
    """Cabang "email udah terdaftar": ga ada kode yg bener, tapi pesan, batas percobaan, & kedaluwarsanya
    dibikin sama persis kayak kode asli. Selalu lempar AuthError; hitungannya disimpen di state (session)."""
    sent_at = datetime.fromtimestamp(state["sent_at"], tz=timezone.utc)
    if state["attempt_count"] >= OTP_MAX_ATTEMPT_COUNT or sent_at + timedelta(minutes=OTP_EXPIRE_MINUTES) < utc_now():
        raise AuthError(OTP_EXPIRED_ERROR)
    state["attempt_count"] += 1
    if state["attempt_count"] >= OTP_MAX_ATTEMPT_COUNT:
        raise AuthError(OTP_EXHAUSTED_ERROR)
    raise AuthError(OTP_WRONG_ERROR)


def verify_registration(state, code):
    """Cek kode verifikasi daftar. Bener -> akun dibikin pake data percobaan INI (bukan percobaan lain), return User.
    Salah kode di sini ga ngunci akun siapa pun (akunnya emang belum ada)."""
    pending = get_pending_registration(state)
    if pending is None:
        check_registration_without_account(state)
    if pending.attempt_count >= OTP_MAX_ATTEMPT_COUNT or to_utc_aware(pending.code_expires_at) < utc_now():
        raise AuthError(OTP_EXPIRED_ERROR)
    if not is_otp_code_match(code, pending.code_hash):
        pending.attempt_count += 1
        db.session.commit()
        raise AuthError(OTP_EXHAUSTED_ERROR if pending.attempt_count >= OTP_MAX_ATTEMPT_COUNT else OTP_WRONG_ERROR)

    clean_email = pending.email
    profile_dict = {key: getattr(pending, key) for key in ("full_name", "department", "job_title", "password_hash")}
    # cuma percobaan INI yg dihapus. Percobaan lain buat email yg sama dibiarin sampe kedaluwarsa (24 jam):
    # kalau pemiliknya masukin kode bener di situ -> "sudah selesai, silakan login", bukan "kode salah" yg bikin bingung
    db.session.delete(pending)
    if find_user_by_email(clean_email) is not None:
        db.session.commit()
        raise RegistrationFinishedError(REGISTRATION_FINISHED_ERROR)
    try:
        user = create_user_account(clean_email, profile_dict, ROLE_USER_ENTRY)
        db.session.commit()
    except IntegrityError:
        # 2 percobaan sah diverifikasi di detik yg sama: yg kalah diarahin login
        db.session.rollback()
        raise RegistrationFinishedError(REGISTRATION_FINISHED_ERROR) from None
    return user


def resend_registration_code(state):
    """Kirim ulang kode verifikasi daftar (jeda 60 dtk). Cabang "email udah terdaftar" ngirim ulang
    email pemberitahuan (tetep dibatasi 10 menit). state di-reset kayak kode baru."""
    sent_at = datetime.fromtimestamp(state["sent_at"], tz=timezone.utc)
    if sent_at + timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS) > utc_now():
        raise AuthError(OTP_COOLDOWN_ERROR)
    pending = get_pending_registration(state)
    if pending is not None:
        if to_utc_aware(pending.last_sent_at) + timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS) > utc_now():
            raise AuthError(OTP_COOLDOWN_ERROR)
        issue_registration_code(pending)
    else:
        user = find_user_by_email(state["email"])
        if user is not None:
            send_registration_notice_safely(user)
    state["sent_at"] = utc_now().timestamp()
    state["attempt_count"] = 0


# LOGIN LANGKAH 1: EMAIL + PASSWORD

@lru_cache(maxsize=1)
def get_dummy_password_hash():
    """Hash palsu buat email yg ga terdaftar, biar waktu responnya sama kayak email asli."""
    return hash_password("dummy-password-cuma-buat-timing-123")


def is_account_locked(user):
    """True kalau akun lagi dikunci (gara-gara kebanyakan salah OTP)."""
    return user.locked_until is not None and to_utc_aware(user.locked_until) > utc_now()


def register_failed_otp(user):
    """Tambah hitungan salah OTP. Kalau nyampe batas, kunci akunnya.
    Salah password ga lewat sini (diblokir per email+IP di auth_throttle), biar orang lain ga bisa ngunci akun kita."""
    user.failed_login_count += 1
    if user.failed_login_count >= LOGIN_MAX_FAILED_COUNT:
        user.locked_until = utc_now() + timedelta(minutes=LOGIN_LOCK_MINUTES)
        # hitungan di-reset, nanti mulai dari 0 lagi pas kunci udah kebuka
        user.failed_login_count = 0


def notify_login_blocked(user, ip_address):
    """Kabarin pemilik akun lewat lonceng: ada yg salah password berkali-kali dari IP tertentu."""
    add_notification(
        user.id,
        f"Ada {LOGIN_MAX_FAILED_COUNT} percobaan login gagal ke akunmu dari IP {ip_address}. "
        "Kalau itu bukan kamu, hubungi admin ICT.",
    )


def authenticate_user(email, password):
    """Cek email + password. Return User kalau bener, lempar AuthError kalau salah.

    Urutannya penting biar ga bocor:
    1. email+IP lagi diblokir -> tolak (pesannya sama buat email terdaftar maupun ngga)
    2. email ga ada / nonaktif / password salah -> pesan generik + catat gagal per email+IP
    3. akun dikunci gara-gara salah OTP -> pesan "dikunci" cuma keluar kalau password-nya bener
    """
    clean_email = normalize_email(email)
    ip_address = auth_throttle.get_client_ip()
    blocked_minute_count = auth_throttle.get_login_block_minutes(clean_email, ip_address)
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
        auth_throttle.record_login_failure(clean_email, ip_address)
        log_audit(AUDIT_ACTION_LOGIN_FAILED, "users", actor_email=clean_email[:255], is_commit=True)
        raise AuthError(GENERIC_LOGIN_ERROR)

    # akun nonaktif atau password salah -> pesannya tetep sama
    if not user.is_active or not verify_password(user.password_hash, password):
        is_newly_blocked = auth_throttle.record_login_failure(clean_email, ip_address)
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

    auth_throttle.clear_login_failure(clean_email, ip_address)
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

def get_latest_otp(user_id, is_unused_only=False):
    """Ambil OTP paling baru milik user (opsional: yg belum kepake aja)."""
    query = db.select(OtpCode).filter_by(user_id=user_id)
    if is_unused_only:
        query = query.filter_by(is_used=False)
    return db.session.execute(query.order_by(OtpCode.id.desc()).limit(1)).scalar_one_or_none()


def is_otp_cooldown_active(user_id):
    """True kalau OTP terakhir baru aja dikirim (belum lewat jeda kirim ulang)."""
    latest_otp = get_latest_otp(user_id)
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
        .where(OtpCode.user_id == user.id, OtpCode.is_used.is_(False))
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
        raise AuthError("OTP belum bisa dikirim. Coba lagi atau hubungi admin.") from None


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
        register_failed_otp(user)
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
