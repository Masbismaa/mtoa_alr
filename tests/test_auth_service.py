"""Test logika register, login password, OTP, dan CLI create-admin."""
from datetime import timedelta

import pytest

from app.extensions import db
from app.models import AuditLog, OtpCode, User
from app.services import auth_service
from app.services.auth_service import (
    authenticate_user,
    register_user,
    resend_otp_challenge,
    start_otp_challenge,
    verify_otp_code,
)
from app.utils.constants import (
    AUDIT_ACTION_CREATE,
    AUDIT_ACTION_LOGIN_FAILED,
    LOGIN_MAX_FAILED_COUNT,
    ROLE_ADMIN,
    ROLE_USER_ENTRY,
)
from app.utils.datetime_helper import utc_now
from app.utils.exceptions import AuthError

def build_register_dict(email="baru@spindo.com", password="PasswordKuat123"):
    """Helper: data register contoh."""
    return {
        "email": email,
        "password": password,
        "full_name": "User Baru",
        "department": "ICT",
        "job_title": "Staff",
    }

def count_audit(action):
    """Helper: hitung audit log dengan aksi tertentu."""
    return db.session.execute(db.select(db.func.count(AuditLog.id)).filter_by(action=action)).scalar()

# register
def test_register_user_success(app):
    """Positive: akun baru jadi user_entry, password di-hash, punya preferensi, kecatat di audit."""
    user = register_user(**build_register_dict())
    assert user.role == ROLE_USER_ENTRY
    assert user.password_hash.startswith("$argon2id$")
    assert user.preference is not None
    assert count_audit(AUDIT_ACTION_CREATE) == 1

def test_register_rejects_other_domain(app):
    """email di luar @spindo.com ditolak."""
    with pytest.raises(AuthError, match="@spindo.com"):
        register_user(**build_register_dict(email="orang@gmail.com"))

def test_register_rejects_duplicate_email(app, registered_user):
    """email yg udah ada (beda huruf besar/kecil) ditolak."""
    with pytest.raises(AuthError, match="sudah terdaftar"):
        register_user(**build_register_dict(email="USER.LOGIN@spindo.com"))

def test_register_rejects_short_password(app):
    """password kependekan ditolak di service juga (bukan cuma di form)."""
    with pytest.raises(AuthError, match="minimal"):
        register_user(**build_register_dict(password="abc1"))

# login password
def test_authenticate_user_success(app, registered_user, user_password):
    """email (dengan spasi & huruf besar) + password bener -> dapet user."""
    user = authenticate_user("  User.Login@Spindo.com ", user_password)
    assert user.id == registered_user.id

def test_authenticate_wrong_password(app, registered_user):
    """password salah -> pesan umum, kecatat audit; akunnya sendiri ga disentuh (yg dihitung email+IP)."""
    with pytest.raises(AuthError, match="Email atau password salah"):
        authenticate_user(registered_user.email, "PasswordSalah1")
    assert registered_user.failed_login_count == 0
    assert count_audit(AUDIT_ACTION_LOGIN_FAILED) == 1

def test_authenticate_unknown_email_same_message(app):
    """email ga terdaftar pesannya sama persis, biar ga bisa ditebak."""
    with pytest.raises(AuthError, match="Email atau password salah"):
        authenticate_user("ga.ada@spindo.com", "PasswordKuat123")

def test_login_blocked_after_max_failed(app, registered_user, user_password):
    """5x salah dari tempat yg sama -> tempat itu diblokir (password bener pun ditolak), tapi akunnya ga dikunci."""
    for _ in range(LOGIN_MAX_FAILED_COUNT):
        with pytest.raises(AuthError):
            authenticate_user(registered_user.email, "PasswordSalah1")
    with pytest.raises(AuthError, match="Terlalu banyak percobaan login"):
        authenticate_user(registered_user.email, user_password)
    assert registered_user.locked_until is None

# OTP
def test_verify_otp_success(app, registered_user, fixed_otp_code):
    """OTP bener -> login kecatat, OTP ditandai kepake."""
    start_otp_challenge(registered_user)
    verify_otp_code(registered_user, fixed_otp_code)
    otp = db.session.execute(db.select(OtpCode)).scalar_one()
    assert otp.is_used is True
    assert registered_user.last_login_at is not None

def test_verify_otp_wrong_code(app, registered_user, fixed_otp_code):
    """OTP salah -> ditolak & percobaannya dihitung."""
    start_otp_challenge(registered_user)
    with pytest.raises(AuthError, match="salah"):
        verify_otp_code(registered_user, "000000")
    otp = db.session.execute(db.select(OtpCode)).scalar_one()
    assert otp.attempt_count == 1

def test_verify_otp_expired(app, registered_user, fixed_otp_code):
    """OTP yg udah lewat 5 menit ditolak."""
    start_otp_challenge(registered_user)
    otp = db.session.execute(db.select(OtpCode)).scalar_one()
    otp.expires_at = utc_now() - timedelta(minutes=1)
    db.session.commit()
    with pytest.raises(AuthError, match="kedaluwarsa"):
        verify_otp_code(registered_user, fixed_otp_code)

def test_new_otp_invalidates_old_otp(app, registered_user, monkeypatch):
    """OTP lama ga bisa dipake lagi setelah OTP baru dibuat."""
    code_iter = iter(["111111", "222222"])
    monkeypatch.setattr(auth_service, "generate_otp_code", lambda: next(code_iter))
    start_otp_challenge(registered_user)
    start_otp_challenge(registered_user)
    with pytest.raises(AuthError):
        verify_otp_code(registered_user, "111111")
    assert verify_otp_code(registered_user, "222222").id == registered_user.id

def test_resend_otp_must_wait_cooldown(app, registered_user, fixed_otp_code):
    """minta OTP baru langsung setelah dikirim ditolak (anti spam)."""
    start_otp_challenge(registered_user)
    with pytest.raises(AuthError, match="Tunggu"):
        resend_otp_challenge(registered_user)

def test_otp_printed_to_terminal_in_console_mode(app, registered_user, fixed_otp_code, capsys):
    """mode console -> OTP muncul di terminal."""
    start_otp_challenge(registered_user)
    captured = capsys.readouterr()
    assert fixed_otp_code in captured.out
    assert registered_user.email in captured.out

# CLI
def test_cli_create_admin(app):
    """perintah create-admin bikin akun ber-role admin."""
    result = app.test_cli_runner().invoke(args=[
        "create-admin",
        "--email", "admin.alr@spindo.com",
        "--full-name", "Admin ALR",
        "--department", "ICT",
        "--job-title", "Manager",
        "--password", "AdminKuat123",
    ])
    assert result.exit_code == 0, result.output
    admin = db.session.execute(db.select(User).filter_by(email="admin.alr@spindo.com")).scalar_one()
    assert admin.role == ROLE_ADMIN

def test_wrong_otp_counts_toward_account_lock(app, registered_user, fixed_otp_code):
    """Negative (security): salah OTP terus-terusan ikut ngunci akun, OTP bener pun ditolak."""
    start_otp_challenge(registered_user)
    for _ in range(LOGIN_MAX_FAILED_COUNT - 1):
        with pytest.raises(AuthError, match="salah"):
            verify_otp_code(registered_user, "000000")
    with pytest.raises(AuthError, match="dikunci"):
        verify_otp_code(registered_user, "000000")
    assert registered_user.locked_until is not None
    with pytest.raises(AuthError, match="dikunci"):
        verify_otp_code(registered_user, fixed_otp_code)

def test_password_failures_do_not_count_toward_account_lock(app, registered_user, user_password, fixed_otp_code):
    """Negative (security): salah password (bisa dilakuin siapa aja) ga ikut ngunci akun; kunci akun cuma dari salah OTP."""
    for _ in range(LOGIN_MAX_FAILED_COUNT - 1):
        with pytest.raises(AuthError):
            authenticate_user(registered_user.email, "PasswordSalah1")
    start_otp_challenge(authenticate_user(registered_user.email, user_password))
    with pytest.raises(AuthError, match="Kode OTP salah"):
        verify_otp_code(registered_user, "000000")
    assert registered_user.locked_until is None

def test_inactive_user_cannot_finish_otp(app, registered_user, fixed_otp_code):
    """Negative: akun dinonaktifin pas lagi di halaman OTP -> ditolak walau OTP-nya bener."""
    start_otp_challenge(registered_user)
    registered_user.is_active = False
    db.session.commit()
    with pytest.raises(AuthError, match="tidak aktif"):
        verify_otp_code(registered_user, fixed_otp_code)

def test_locked_user_cannot_resend_otp(app, registered_user):
    """Negative: akun yg lagi dikunci ga bisa minta OTP baru."""
    registered_user.locked_until = utc_now() + timedelta(minutes=5)
    db.session.commit()
    with pytest.raises(AuthError, match="dikunci"):
        resend_otp_challenge(registered_user)