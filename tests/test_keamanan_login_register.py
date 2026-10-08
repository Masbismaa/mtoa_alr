"""Test celah login & daftar:
- salah password diblokir per email+IP (orang lain ga bisa ngunci akun kita)
- daftar wajib verifikasi email (akun baru dibikin setelah kode bener, per percobaan daftar),
  dan layar ga ngebocorin email mana yg udah terdaftar
"""
import re
from datetime import timedelta

import pytest

from app.extensions import db
from app.models import AuditLog, PendingRegistration, User, UserNotification
from app.services import auth_service, notification_service
from app.services.auth_service import check_registration_without_account, verify_registration
from app.utils.constants import (
    AUDIT_ACTION_CREATE,
    LOGIN_MAX_FAILED_COUNT,
    OTP_MAX_ATTEMPT_COUNT,
    REGISTER_CODE_MAX_COUNT,
    SESSION_PENDING_REGISTER_KEY,
)
from app.utils.datetime_helper import utc_now
from app.utils.exceptions import AuthError

ATTACKER_IP = "10.0.0.66"
OWNER_IP = "10.0.0.7"
WRONG_PASSWORD = "PasswordSalah1"
# panjang & 2 huruf depan sama kayak user.login -> email samarannya sama persis (us********@spindo.com)
NEW_EMAIL = "us.new.abc@spindo.com"

def post_login(client, email, password, ip_address):
    return client.post("/auth/login", data={"email": email, "password": password},
                       environ_base={"REMOTE_ADDR": ip_address})

def post_register(client, email, password="PasswordKuat123", full_name="User Baru"):
    return client.post("/auth/register", data={
        "email": email, "full_name": full_name, "department": "ICT", "job_title": "Staff",
        "password": password, "confirm_password": password,
    })

def normalize_page(response):
    """Isi halaman tanpa token CSRF (acak per session) biar 2 halaman bisa dibandingin persis."""
    return re.sub(r'name="csrf_token" value="[^"]*"', 'name="csrf_token" value=""', response.get_data(as_text=True))

def find_user(email):
    return db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()

# LOCKOUT PER EMAIL + IP

def test_attacker_ip_blocked_but_owner_can_still_login(client, registered_user, user_password, fixed_otp_code):
    """Positive & negative (security): 5x salah dari IP penyerang -> IP itu diblokir, pemilik dari IP lain tetep masuk."""
    for _ in range(LOGIN_MAX_FAILED_COUNT):
        assert "Email atau password salah" in post_login(client, registered_user.email, WRONG_PASSWORD, ATTACKER_IP).get_data(as_text=True)
    blocked_response = post_login(client, registered_user.email, user_password, ATTACKER_IP)
    assert "Terlalu banyak percobaan login dari perangkat ini" in blocked_response.get_data(as_text=True)

    owner_response = post_login(client, registered_user.email, user_password, OWNER_IP)
    assert owner_response.status_code == 302
    assert "/auth/otp" in owner_response.location
    assert find_user(registered_user.email).locked_until is None

def test_unknown_email_blocked_with_same_message(client):
    """Negative (security): email ga terdaftar juga diblokir dgn pesan yg sama, jadi blokir ga ngebocorin email terdaftar."""
    for _ in range(LOGIN_MAX_FAILED_COUNT):
        post_login(client, "ga.ada@spindo.com", WRONG_PASSWORD, ATTACKER_IP)
    response = post_login(client, "ga.ada@spindo.com", WRONG_PASSWORD, ATTACKER_IP)
    assert "Terlalu banyak percobaan login dari perangkat ini" in response.get_data(as_text=True)

def test_owner_notified_once_with_attacker_ip(client, registered_user):
    """Positive: pemilik akun dapet 1 notifikasi lonceng berisi IP penyerang, ga dobel walau diserang terus."""
    for _ in range(LOGIN_MAX_FAILED_COUNT + 3):
        post_login(client, registered_user.email, WRONG_PASSWORD, ATTACKER_IP)
    message_list = db.session.execute(
        db.select(UserNotification.message).filter_by(user_id=registered_user.id)
    ).scalars().all()
    assert len(message_list) == 1
    assert ATTACKER_IP in message_list[0]

def test_success_clears_failure_count(client, registered_user, user_password):
    """Positive: login bener ngereset hitungan, jadi salah ketik sesekali ga numpuk sampe keblokir."""
    for _ in range(LOGIN_MAX_FAILED_COUNT - 1):
        post_login(client, registered_user.email, WRONG_PASSWORD, OWNER_IP)
    assert post_login(client, registered_user.email, user_password, OWNER_IP).status_code == 302
    for _ in range(LOGIN_MAX_FAILED_COUNT - 1):
        post_login(client, registered_user.email, WRONG_PASSWORD, OWNER_IP)
    assert post_login(client, registered_user.email, user_password, OWNER_IP).status_code == 302

def test_otp_lock_message_needs_correct_password(client, registered_user, user_password):
    """Negative (security): akun kekunci (salah OTP) cuma ketauan sama yg tau password-nya."""
    registered_user.locked_until = utc_now() + timedelta(minutes=10)
    db.session.commit()
    wrong_text = post_login(client, registered_user.email, WRONG_PASSWORD, ATTACKER_IP).get_data(as_text=True)
    assert "Email atau password salah" in wrong_text
    assert "dikunci" not in wrong_text
    assert "dikunci" in post_login(client, registered_user.email, user_password, OWNER_IP).get_data(as_text=True)

def test_block_works_while_rate_limit_disabled(app, client, registered_user):
    """Positive: pembatas login tetep jalan walau rate limit Flask-Limiter dimatiin (kayak di config test)."""
    assert app.config["RATELIMIT_ENABLED"] is False
    for _ in range(LOGIN_MAX_FAILED_COUNT):
        post_login(client, registered_user.email, WRONG_PASSWORD, ATTACKER_IP)
    assert "Terlalu banyak" in post_login(client, registered_user.email, WRONG_PASSWORD, ATTACKER_IP).get_data(as_text=True)

# DAFTAR + VERIFIKASI EMAIL

def use_code_sequence(monkeypatch, *code_list):
    """Kode verifikasi/OTP yg keluar berurutan sesuai daftar (biar bisa bedain kode punya siapa)."""
    code_iter = iter(code_list)
    monkeypatch.setattr(auth_service, "generate_otp_code", lambda: next(code_iter))

def count_pending(email):
    return db.session.scalar(db.select(db.func.count(PendingRegistration.id)).filter_by(email=email))

def test_register_verify_then_login(client, fixed_otp_code, user_password):
    """Positive: daftar -> masukin kode dari email -> akun BARU dibikin, kecatat audit, percobaannya dihapus -> bisa login."""
    post_register(client, NEW_EMAIL, password=user_password)
    assert find_user(NEW_EMAIL) is None
    response = client.post("/auth/register/verify", data={"otp_code": fixed_otp_code})
    assert response.status_code == 302
    assert "/auth/login" in response.location
    user = find_user(NEW_EMAIL)
    assert user.full_name == "User Baru"
    assert db.session.scalar(db.select(db.func.count(AuditLog.id)).filter_by(action=AUDIT_ACTION_CREATE, user_id=user.id)) == 1
    assert count_pending(NEW_EMAIL) == 0
    assert "/auth/otp" in post_login(client, NEW_EMAIL, user_password, OWNER_IP).location

def test_unverified_registration_cannot_login(client, user_password):
    """Negative (security): belum masukin kode -> akunnya belum ada, login ditolak dgn pesan biasa."""
    post_register(client, NEW_EMAIL, password=user_password)
    response = post_login(client, NEW_EMAIL, user_password, OWNER_IP)
    assert response.status_code == 200
    assert "Email atau password salah" in response.get_data(as_text=True)

@pytest.mark.parametrize("is_cooldown_skipped", [False, True])
def test_owner_keeps_own_password_when_someone_registers_later(app, monkeypatch, is_cooldown_skipped):
    """Negative (security, temuan audit): pemilik daftar (password A) -> orang lain daftar email yg sama (password B)
    -> kode punya orang itu nyasar ke email pemilik & dimasukin di halaman pemilik = "salah";
    pemilik masukin kodenya sendiri -> akun jadi pake password A & nama pemilik, password B ga berlaku.
    Diuji dgn jeda kirim ulang normal maupun dilewatin."""
    use_code_sequence(monkeypatch, "111111", "222222", "333333")
    if is_cooldown_skipped:
        monkeypatch.setattr(auth_service, "OTP_RESEND_COOLDOWN_SECONDS", 0)
    owner_client, other_client = app.test_client(), app.test_client()
    post_register(owner_client, NEW_EMAIL, password="PasswordPemilik1", full_name="Pemilik Asli")
    post_register(other_client, NEW_EMAIL, password="PasswordOrangLain2", full_name="Orang Lain")

    wrong_text = owner_client.post("/auth/register/verify", data={"otp_code": "222222"}).get_data(as_text=True)
    assert "Kode OTP salah" in wrong_text
    assert "/auth/login" in owner_client.post("/auth/register/verify", data={"otp_code": "111111"}).location

    user = find_user(NEW_EMAIL)
    assert user.full_name == "Pemilik Asli"
    assert "/auth/otp" in post_login(owner_client, NEW_EMAIL, "PasswordPemilik1", OWNER_IP).location
    assert "Email atau password salah" in post_login(other_client, NEW_EMAIL, "PasswordOrangLain2", ATTACKER_IP).get_data(as_text=True)

def test_other_attempt_cannot_change_finished_account(app, monkeypatch):
    """Negative (security): akun udah jadi -> percobaan orang lain yg masih nunggu ga bisa ngubah apa-apa
    (tanpa kode yg bener cuma dapet "salah")."""
    use_code_sequence(monkeypatch, "111111", "222222")
    owner_client, other_client = app.test_client(), app.test_client()
    post_register(owner_client, NEW_EMAIL, password="PasswordPemilik1", full_name="Pemilik Asli")
    post_register(other_client, NEW_EMAIL, password="PasswordOrangLain2", full_name="Orang Lain")
    owner_client.post("/auth/register/verify", data={"otp_code": "111111"})
    old_password_hash = find_user(NEW_EMAIL).password_hash
    assert "Kode OTP salah" in other_client.post("/auth/register/verify", data={"otp_code": "999999"}).get_data(as_text=True)
    user = find_user(NEW_EMAIL)
    assert (user.full_name, user.password_hash) == ("Pemilik Asli", old_password_hash)

def test_second_own_attempt_after_account_made_goes_to_login(app, monkeypatch):
    """Positive: pemilik sempet daftar 2x (2 browser), 1 udah diverifikasi -> kode bener di browser satunya
    diarahin login "sudah selesai", ga bikin akun dobel."""
    use_code_sequence(monkeypatch, "111111", "222222")
    first_client, second_client = app.test_client(), app.test_client()
    post_register(first_client, NEW_EMAIL)
    post_register(second_client, NEW_EMAIL)
    first_client.post("/auth/register/verify", data={"otp_code": "111111"})
    response = second_client.post("/auth/register/verify", data={"otp_code": "222222"}, follow_redirects=True)
    assert "Pendaftaran untuk email ini sudah selesai" in response.get_data(as_text=True)
    assert db.session.scalar(db.select(db.func.count(User.id)).filter_by(email=NEW_EMAIL)) == 1
    assert count_pending(NEW_EMAIL) == 0

def test_new_and_existing_email_look_identical(app, registered_user):
    """Negative (security/enumerasi): daftar pakai email baru vs email yg udah terdaftar -> redirect, halaman,
    pesan salah kode, batas percobaan, dan kedaluwarsa sama persis."""
    new_client, existing_client = app.test_client(), app.test_client()
    new_response = post_register(new_client, NEW_EMAIL)
    existing_response = post_register(existing_client, registered_user.email)
    assert (new_response.status_code, new_response.location) == (existing_response.status_code, existing_response.location)
    assert normalize_page(new_client.get("/auth/register/verify")) == normalize_page(existing_client.get("/auth/register/verify"))
    for _ in range(OTP_MAX_ATTEMPT_COUNT + 1):
        new_page = normalize_page(new_client.post("/auth/register/verify", data={"otp_code": "000000"}))
        existing_page = normalize_page(existing_client.post("/auth/register/verify", data={"otp_code": "000000"}))
        assert new_page == existing_page
    # kirim ulang langsung (masih jeda) -> pesannya juga sama
    new_resend = new_client.post("/auth/register/resend", follow_redirects=True)
    existing_resend = existing_client.post("/auth/register/resend", follow_redirects=True)
    assert normalize_page(new_resend) == normalize_page(existing_resend)
    assert "Tunggu sebentar" in new_resend.get_data(as_text=True)

def test_existing_account_untouched_and_owner_notified_once(client, registered_user, capsys):
    """Negative (security): daftar pakai email orang yg udah punya akun ga ngubah akunnya & ga nyimpen percobaan;
    pemiliknya dapet email pemberitahuan, maksimal sekali per 10 menit (anti spam)."""
    old_password_hash = registered_user.password_hash
    post_register(client, registered_user.email, password="PasswordPenyerang9", full_name="Penyerang")
    post_register(client, registered_user.email, password="PasswordPenyerang9", full_name="Penyerang")
    user = find_user(registered_user.email)
    assert (user.password_hash, user.full_name) == (old_password_hash, "User Login")
    assert count_pending(registered_user.email) == 0
    assert capsys.readouterr().out.count("Percobaan pendaftaran ALR") == 1

def test_wrong_registration_code_exhausts_then_expires(client, fixed_otp_code):
    """Negative: salah kode sampe habis -> "terlalu banyak", kode bener pun udah ga berlaku (minta baru)."""
    post_register(client, NEW_EMAIL)
    for _ in range(OTP_MAX_ATTEMPT_COUNT):
        response = client.post("/auth/register/verify", data={"otp_code": "000000"})
    assert "Terlalu banyak percobaan OTP" in response.get_data(as_text=True)
    assert "kedaluwarsa" in client.post("/auth/register/verify", data={"otp_code": fixed_otp_code}).get_data(as_text=True)
    assert find_user(NEW_EMAIL) is None

def test_resend_gives_new_code_after_cooldown(client, monkeypatch):
    """Positive: kirim ulang (abis jeda) -> kode lama ga berlaku, kode baru bisa dipake."""
    use_code_sequence(monkeypatch, "111111", "222222")
    post_register(client, NEW_EMAIL)
    monkeypatch.setattr(auth_service, "OTP_RESEND_COOLDOWN_SECONDS", 0)
    assert "Kode verifikasi baru sudah dikirim" in client.post("/auth/register/resend", follow_redirects=True).get_data(as_text=True)
    assert "Kode OTP salah" in client.post("/auth/register/verify", data={"otp_code": "111111"}).get_data(as_text=True)
    assert "/auth/login" in client.post("/auth/register/verify", data={"otp_code": "222222"}).location

def test_register_code_limited_per_email(app, capsys):
    """Negative (anti spam): kode daftar ke 1 email maksimal 5x / 15 menit, walau percobaannya dari banyak session."""
    for _ in range(REGISTER_CODE_MAX_COUNT + 2):
        post_register(app.test_client(), NEW_EMAIL)
    assert capsys.readouterr().out.count("Kode verifikasi pendaftaran ALR:") == REGISTER_CODE_MAX_COUNT

def test_expired_pending_registration_cleaned_up(client):
    """Positive: percobaan daftar yg udah lewat 24 jam dibuang pas ada yg daftar lagi (tabel ga numpuk)."""
    post_register(client, NEW_EMAIL)
    db.session.execute(db.update(PendingRegistration).values(created_at=utc_now() - timedelta(hours=25)))
    db.session.commit()
    post_register(client, "orang.lain@spindo.com")
    assert count_pending(NEW_EMAIL) == 0
    assert count_pending("orang.lain@spindo.com") == 1

def test_old_session_format_asks_to_register_again(client):
    """Negative: session pendaftaran format lama (tanpa token) dianggap habis, bukan error 500."""
    with client.session_transaction() as session:
        session[SESSION_PENDING_REGISTER_KEY] = {"email": NEW_EMAIL, "sent_at": 0, "attempt_count": 0}
    response = client.post("/auth/register/verify", data={"otp_code": "123456"})
    assert response.status_code == 302
    assert "/auth/register" in response.location

def test_registration_without_account_expires_like_real_code(app):
    """Positive: cabang email udah terdaftar ikut "kedaluwarsa" setelah 5 menit, sama kayak kode asli."""
    state = {"email": "x@spindo.com", "token": "token-ga-ada", "sent_at": (utc_now() - timedelta(minutes=6)).timestamp(),
             "attempt_count": 0}
    with pytest.raises(AuthError, match="kedaluwarsa"):
        check_registration_without_account(state)
    with pytest.raises(AuthError, match="kedaluwarsa"):
        verify_registration(state, "000000")

def test_smtp_failure_on_register_looks_the_same(app, registered_user, monkeypatch):
    """Negative (security): SMTP mati -> daftar email baru tetep keliatan sukses kayak email lama
    (error-nya cuma di log), biar gangguan SMTP ga ngebocorin email terdaftar."""
    def fail_delivery(*args):
        raise OSError("smtp mati")
    monkeypatch.setattr(auth_service, "send_otp_code", fail_delivery)
    monkeypatch.setattr(notification_service, "send_email", fail_delivery)
    new_client, existing_client = app.test_client(), app.test_client()
    post_register(new_client, NEW_EMAIL)
    post_register(existing_client, registered_user.email)
    new_page = normalize_page(new_client.get("/auth/register/verify"))
    assert new_page == normalize_page(existing_client.get("/auth/register/verify"))
    assert "belum bisa dikirim" not in new_page
