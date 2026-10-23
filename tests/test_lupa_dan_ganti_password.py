"""Test lupa password, ganti password di Settings, & edit profil:
- lupa password ga bocorin email mana yg terdaftar, kodenya kepisah dari OTP login, salah kode ga ngunci akun
- password keganti (lewat mana pun) -> semua sesi lain ke-logout, dicatat di audit, pemilik dikabarin
"""
import pytest
from flask import g

from app.extensions import db
from app.models import AuditLog, User, UserNotification
from app.services import auth_service
from app.services.auth_service import AuthError
from app.utils.constants import (
    AUDIT_ACTION_PASSWORD_CHANGE,
    AUDIT_ACTION_UPDATE,
    LOGIN_MAX_FAILED_COUNT,
    OTP_MAX_ATTEMPT_COUNT,
    REGISTER_CODE_MAX_COUNT,
    SESSION_PASSWORD_RESET_KEY,
)
from tests.conftest import USER_PASSWORD, login_client
from tests.test_keamanan_login_register import NEW_EMAIL, normalize_page

NEW_PASSWORD = "PasswordBaru456"
# baris judul email di output mode console (judulnya juga muncul di isi email, jadi yg dihitung baris ini)
RESET_EMAIL_LINE = "ALR password reset code ====="


def as_client(client):
    """Flask-Login nyimpen user yg login di g, dan semua request test berbagi 1 app context (fixture app).
    Ganti-ganti client (sesi berbeda) -> buang dulu cache-nya biar tiap client dibaca dari cookie-nya sendiri."""
    g.pop("_login_user", None)
    return client


def use_code_sequence(monkeypatch, *code_list):
    """OTP yg dibikin berurutan pake kode ini (biar kode reset & kode login beda)."""
    code_iter = iter(code_list)
    monkeypatch.setattr(auth_service, "generate_otp_code", lambda: next(code_iter))


def request_reset(client, email):
    return client.post("/auth/forgot", data={"email": email}, follow_redirects=True)


def submit_reset(client, code, password=NEW_PASSWORD):
    return client.post("/auth/reset", data={"otp_code": code, "password": password, "confirm_password": password})


def find_audit(action):
    return db.session.execute(db.select(AuditLog).filter_by(action=action)).scalars().all()


# LUPA PASSWORD

def test_forgot_password_page_same_for_registered_and_unknown_email(app, registered_user, capsys):
    """Negative (security): email terdaftar & ga terdaftar -> layar sama persis, kode cuma kekirim ke yg terdaftar."""
    registered_page = request_reset(app.test_client(), registered_user.email)
    # NEW_EMAIL samarannya sama persis kayak user.login (us********@spindo.com), jadi halamannya bisa dibandingin utuh
    unknown_page = request_reset(app.test_client(), NEW_EMAIL)
    assert registered_page.request.path == unknown_page.request.path == "/auth/reset"
    assert normalize_page(registered_page) == normalize_page(unknown_page)
    assert "If the email is registered" in registered_page.get_data(as_text=True)
    assert capsys.readouterr().out.count(RESET_EMAIL_LINE) == 1


def test_reset_password_full_flow(client, registered_user, fixed_otp_code, capsys):
    """Positive: kode bener -> password baru berlaku, yg lama nggak, audit + lonceng + email pemberitahuan."""
    old_version = registered_user.session_version
    request_reset(client, registered_user.email)
    response = submit_reset(client, fixed_otp_code)
    assert response.status_code == 302 and response.location.endswith("/auth/login")
    with client.session_transaction() as flask_session:
        assert SESSION_PASSWORD_RESET_KEY not in flask_session
    user = db.session.get(User, registered_user.id)
    assert user.session_version == old_version + 1
    with pytest.raises(AuthError):
        auth_service.authenticate_user(user.email, USER_PASSWORD)
    assert auth_service.authenticate_user(user.email, NEW_PASSWORD).id == user.id
    assert [log.new_data for log in find_audit(AUDIT_ACTION_PASSWORD_CHANGE)] == [{"method": "reset"}]
    assert db.session.execute(db.select(UserNotification).filter_by(user_id=user.id)).scalars().first() is not None
    assert "ALR password changed" in capsys.readouterr().out


def test_reset_logs_out_other_sessions(app, registered_user, fixed_otp_code):
    """Negative (security): sesi yg lagi login (mungkin punya penyerang) ke-logout begitu password di-reset."""
    old_session = login_client(as_client(app.test_client()), registered_user.email, fixed_otp_code)
    assert as_client(old_session).get("/").status_code == 200
    reset_client = as_client(app.test_client())
    request_reset(reset_client, registered_user.email)
    submit_reset(reset_client, fixed_otp_code)
    response = as_client(old_session).get("/")
    assert response.status_code == 302 and "/auth/login" in response.location


def test_reset_code_and_login_otp_are_separate(app, client, registered_user, monkeypatch):
    """Negative (security): kode reset ga bisa buat login & OTP login ga bisa buat reset; minta OTP login ga ngehanguskan kode reset."""
    use_code_sequence(monkeypatch, "111111", "222222")
    request_reset(client, registered_user.email)
    auth_service.start_otp_challenge(registered_user)
    with pytest.raises(AuthError, match="Incorrect OTP code"):
        auth_service.verify_otp_code(registered_user, "111111")
    assert "Incorrect OTP code" in submit_reset(client, "222222").get_data(as_text=True)
    assert submit_reset(client, "111111").status_code == 302


def test_wrong_reset_code_does_not_lock_account(client, registered_user, fixed_otp_code):
    """Negative (security): salah kode reset sampe habis -> kodenya hangus, tapi akun pemilik ga dikunci."""
    request_reset(client, registered_user.email)
    for _ in range(OTP_MAX_ATTEMPT_COUNT):
        response = submit_reset(client, "000000")
    assert "Too many OTP attempts" in response.get_data(as_text=True)
    assert "expired" in submit_reset(client, fixed_otp_code).get_data(as_text=True)
    user = db.session.get(User, registered_user.id)
    assert user.locked_until is None
    assert auth_service.authenticate_user(user.email, USER_PASSWORD).id == user.id


def test_unknown_email_reset_never_succeeds_and_looks_real(client):
    """Negative (security): email ga terdaftar -> pesan salah kode sama kayak asli, ga pernah berhasil."""
    request_reset(client, "tidak.ada@spindo.com")
    assert "Incorrect OTP code" in submit_reset(client, "123456").get_data(as_text=True)
    for _ in range(OTP_MAX_ATTEMPT_COUNT):
        response = submit_reset(client, "123456")
    assert response.status_code == 200
    assert db.session.execute(db.select(User).filter_by(email="tidak.ada@spindo.com")).scalar_one_or_none() is None


def test_inactive_account_gets_no_reset_code(client, registered_user, capsys):
    """Negative: akun nonaktif diperlakuin kayak ga terdaftar (ga dapet kode)."""
    registered_user.is_active = False
    db.session.commit()
    request_reset(client, registered_user.email)
    assert RESET_EMAIL_LINE not in capsys.readouterr().out


def test_reset_code_emails_limited_per_email(app, registered_user, capsys):
    """Negative (anti spam): minta reset berkali-kali dari banyak session -> email kode dibatasi per alamat."""
    for _ in range(REGISTER_CODE_MAX_COUNT + 3):
        request_reset(app.test_client(), registered_user.email)
    assert capsys.readouterr().out.count(RESET_EMAIL_LINE) == REGISTER_CODE_MAX_COUNT


def test_reset_without_session_redirects_to_forgot(client):
    """Negative: buka halaman reset tanpa minta kode dulu -> balik ke lupa password."""
    response = client.get("/auth/reset")
    assert response.status_code == 302 and response.location.endswith("/auth/forgot")


def test_login_page_links_to_forgot_password(client):
    """Positive: halaman login ada link Forgot password."""
    assert 'href="/auth/forgot"' in client.get("/auth/login").get_data(as_text=True)


# GANTI PASSWORD DI SETTINGS

def change_password_request(client, current=USER_PASSWORD, new=NEW_PASSWORD):
    return client.post("/settings/password", data={
        "current_password": current, "password": new, "confirm_password": new,
    }, follow_redirects=True)


def test_change_password_keeps_this_session_and_logs_out_others(app, registered_user, fixed_otp_code, capsys):
    """Positive: sesi yg ganti tetep login, sesi lain ke-logout, password baru berlaku, audit + email."""
    this_session = login_client(as_client(app.test_client()), registered_user.email, fixed_otp_code)
    other_session = login_client(as_client(app.test_client()), registered_user.email, fixed_otp_code)
    response = change_password_request(as_client(this_session))
    assert "Password changed" in response.get_data(as_text=True)
    assert as_client(this_session).get("/").status_code == 200
    assert "/auth/login" in as_client(other_session).get("/").location
    assert auth_service.authenticate_user(registered_user.email, NEW_PASSWORD).id == registered_user.id
    assert [log.new_data for log in find_audit(AUDIT_ACTION_PASSWORD_CHANGE)] == [{"method": "settings"}]
    assert "ALR password changed" in capsys.readouterr().out


def test_change_password_wrong_current_counts_toward_block(app, logged_in_client, registered_user):
    """Negative (security): password lama salah ditolak, & kalau diulang-ulang ikut keblokir kayak login."""
    for _ in range(LOGIN_MAX_FAILED_COUNT):
        response = change_password_request(logged_in_client, current="SalahTerus123")
    assert "Current password is incorrect" in response.get_data(as_text=True)
    blocked = change_password_request(logged_in_client, current=USER_PASSWORD)
    assert "Too many login attempts" in blocked.get_data(as_text=True)
    # akunnya ikut kekunci (status Locked), sama kayak salah password pas login
    assert db.session.get(User, registered_user.id).locked_until is not None


def test_change_password_same_as_current_rejected(logged_in_client):
    """Negative: password baru sama kayak yg lama ditolak."""
    response = change_password_request(logged_in_client, new=USER_PASSWORD)
    assert "must be different" in response.get_data(as_text=True)


def test_change_password_requires_login(client):
    """Negative: belum login ga bisa ganti password."""
    assert "/auth/login" in client.post("/settings/password", data={}).location


# EDIT PROFIL

def test_update_profile_saves_sanitized_and_audited(logged_in_client, registered_user):
    """Positive: profil keganti (tag HTML dibuang), email & role ga ikut berubah walau dikirim, dicatat audit."""
    response = logged_in_client.post("/settings/profile", data={
        "full_name": "<b>Nama Baru</b>", "department": "Finance", "job_title": "Supervisor",
        "email": "hack@spindo.com", "role": "admin",
    }, follow_redirects=True)
    assert "Profile saved" in response.get_data(as_text=True)
    user = db.session.get(User, registered_user.id)
    assert (user.full_name, user.department, user.job_title) == ("Nama Baru", "Finance", "Supervisor")
    assert (user.email, user.role) == ("user.login@spindo.com", "user_entry")
    audit_log = find_audit(AUDIT_ACTION_UPDATE)[-1]
    assert audit_log.old_data["department"] == "ICT" and audit_log.new_data["department"] == "Finance"


def test_update_profile_empty_rejected(logged_in_client, registered_user):
    """Negative: nama kosong ditolak, profil ga berubah."""
    response = logged_in_client.post("/settings/profile", data={"full_name": "  ", "department": "X", "job_title": "Y"})
    assert response.status_code == 200
    assert db.session.get(User, registered_user.id).full_name == "User Login"


def test_reset_attempts_limited_per_email_across_new_codes(app, registered_user, monkeypatch):
    """Negative (security): minta kode baru terus ga bikin tebakan tanpa batas dari 1 perangkat; email ga terdaftar
    kena batas yg sama."""
    from app.utils.constants import RESET_ATTEMPT_MAX_COUNT

    use_code_sequence(monkeypatch, *[f"{index:06d}" for index in range(100, 200)])
    for email in (registered_user.email, NEW_EMAIL):
        client = app.test_client()
        request_reset(client, email)
        for _ in range(RESET_ATTEMPT_MAX_COUNT):
            submit_reset(client, "999999")
        assert "Too many reset attempts" in submit_reset(client, "999999").get_data(as_text=True)


def test_reset_guesses_from_other_device_do_not_block_owner(app, registered_user, monkeypatch):
    """Negative (security, temuan audit): orang lain salahin kode reset sampe kena batas -> pemilik akun
    (perangkat lain) tetep bisa reset hari itu."""
    from app.utils.constants import RESET_ATTEMPT_MAX_COUNT

    use_code_sequence(monkeypatch, "111111", "222222")
    attacker = app.test_client()
    attacker.environ_base["REMOTE_ADDR"] = "203.0.113.9"
    request_reset(attacker, registered_user.email)
    for _ in range(RESET_ATTEMPT_MAX_COUNT):
        submit_reset(attacker, "999999")
    assert "Too many reset attempts" in submit_reset(attacker, "999999").get_data(as_text=True)

    owner = app.test_client()
    request_reset(owner, registered_user.email)
    response = submit_reset(owner, "222222")
    assert response.status_code == 302 and "/auth/login" in response.location


def test_change_password_cancels_pending_login_and_codes(app, registered_user, fixed_otp_code):
    """Negative (security, temuan audit): orang yg udah lolos password lama & lagi nunggu OTP -> pemilik ganti
    password -> login itu batal walau kode OTP-nya bener, dan semua OTP yg masih aktif hangus."""
    from app.models import OtpCode

    intruder = app.test_client()
    intruder.post("/auth/login", data={"email": registered_user.email, "password": USER_PASSWORD})
    auth_service.change_password(registered_user, USER_PASSWORD, NEW_PASSWORD)

    response = intruder.post("/auth/otp", data={"otp_code": fixed_otp_code})
    assert response.status_code == 302 and "/auth/login" in response.location
    assert db.session.execute(
        db.select(OtpCode).filter_by(user_id=registered_user.id, is_used=False)
    ).first() is None
