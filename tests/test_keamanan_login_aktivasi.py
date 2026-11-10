"""Test celah login & akun baru:
- salah password LOGIN_MAX_FAILED_COUNT kali -> akun dikunci (status Locked) & bisa dibuka admin
- akun baru cuma dibikin admin, aktif setelah pemiliknya bikin password lewat link aktivasi di email
"""
import re
from datetime import timedelta

from flask import g

from app.extensions import db
from app.models import AuditLog, OtpCode, User, UserNotification
from app.services import auth_service
from app.utils.constants import (
    AUDIT_ACTION_CREATE,
    AUDIT_ACTION_PASSWORD_CHANGE,
    LOGIN_MAX_FAILED_COUNT,
    OTP_PURPOSE_ACTIVATION,
    ROLE_ADMIN,
    ROLE_USER_ENTRY,
    USER_STATUS_PENDING,
)
from app.utils.datetime_helper import utc_now

ATTACKER_IP = "10.0.0.66"
OWNER_IP = "10.0.0.7"
WRONG_PASSWORD = "PasswordSalah1"
# panjang & 2 huruf depan sama kayak user.login -> email samarannya sama persis (us********@spindo.com)
NEW_EMAIL = "us.new.abc@spindo.com"

def post_login(client, email, password, ip_address):
    return client.post("/auth/login", data={"email": email, "password": password},
                       environ_base={"REMOTE_ADDR": ip_address})

def normalize_page(response):
    """Isi halaman tanpa token CSRF (acak per session) biar 2 halaman bisa dibandingin persis."""
    return re.sub(r'name="csrf_token" value="[^"]*"', 'name="csrf_token" value=""', response.get_data(as_text=True))

def find_user(email):
    return db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()

# LOCKOUT AKUN

def test_wrong_password_locks_account_until_admin_unlock(client, registered_user, admin_user, user_password):
    """Positive & negative (security): 3x salah password -> akun Locked (dari IP mana pun ditolak), admin unlock -> bisa login."""
    from app.services.user_service import get_user_status, unlock_user
    from app.utils.constants import USER_STATUS_LOCKED

    assert LOGIN_MAX_FAILED_COUNT == 3
    for _ in range(LOGIN_MAX_FAILED_COUNT):
        assert "Incorrect email or password" in post_login(client, registered_user.email, WRONG_PASSWORD, ATTACKER_IP).get_data(as_text=True)
    assert get_user_status(find_user(registered_user.email)) == USER_STATUS_LOCKED
    for ip_address in (ATTACKER_IP, OWNER_IP):
        blocked_response = post_login(client, registered_user.email, user_password, ip_address)
        assert "Too many login attempts" in blocked_response.get_data(as_text=True)

    unlock_user(admin_user, find_user(registered_user.email))
    owner_response = post_login(client, registered_user.email, user_password, OWNER_IP)
    assert owner_response.status_code == 302
    assert "/auth/otp" in owner_response.location

def test_unknown_email_blocked_with_same_message(client, registered_user):
    """Negative (security): email ga terdaftar diblokir dgn pesan yg sama persis kayak akun yg kekunci (ga ngebocorin email terdaftar)."""
    def blocked_text(email):
        for _ in range(LOGIN_MAX_FAILED_COUNT):
            post_login(client, email, WRONG_PASSWORD, ATTACKER_IP)
        return post_login(client, email, WRONG_PASSWORD, ATTACKER_IP).get_data(as_text=True)
    unknown_text = blocked_text("ga.ada@spindo.com")
    assert "Too many login attempts" in unknown_text
    assert "Too many login attempts" in blocked_text(registered_user.email)

def test_owner_notified_once_with_attacker_ip(client, registered_user):
    """Positive: pemilik akun dapet 1 notifikasi lonceng berisi IP penyerang, ga dobel walau diserang terus."""
    for _ in range(LOGIN_MAX_FAILED_COUNT + 3):
        post_login(client, registered_user.email, WRONG_PASSWORD, ATTACKER_IP)
    message_list = db.session.execute(
        db.select(UserNotification.message).filter_by(user_id=registered_user.id)
    ).scalars().all()
    assert len(message_list) == 1
    assert ATTACKER_IP in message_list[0]

def test_success_clears_failure_count(client, registered_user, user_password, fixed_otp_code):
    """Positive: login sampe OTP bener ngereset hitungan, jadi salah ketik sesekali ga numpuk sampe kekunci."""
    for _ in range(LOGIN_MAX_FAILED_COUNT - 1):
        post_login(client, registered_user.email, WRONG_PASSWORD, OWNER_IP)
    assert post_login(client, registered_user.email, user_password, OWNER_IP).status_code == 302
    client.post("/auth/otp", data={"otp_code": fixed_otp_code})
    user = find_user(registered_user.email)
    assert user.failed_login_count == 0 and user.locked_until is None

def test_otp_lock_message_needs_correct_password(client, registered_user, user_password):
    """Negative (security): akun kekunci (salah OTP) cuma ketauan sama yg tau password-nya."""
    registered_user.locked_until = utc_now() + timedelta(minutes=10)
    db.session.commit()
    wrong_text = post_login(client, registered_user.email, WRONG_PASSWORD, ATTACKER_IP).get_data(as_text=True)
    assert "Incorrect email or password" in wrong_text
    assert "locked" not in wrong_text
    assert "locked" in post_login(client, registered_user.email, user_password, OWNER_IP).get_data(as_text=True)

def test_block_works_while_rate_limit_disabled(app, client, registered_user):
    """Positive: pembatas login tetep jalan walau rate limit Flask-Limiter dimatiin (kayak di config test)."""
    assert app.config["RATELIMIT_ENABLED"] is False
    for _ in range(LOGIN_MAX_FAILED_COUNT):
        post_login(client, registered_user.email, WRONG_PASSWORD, ATTACKER_IP)
    assert "Too many" in post_login(client, registered_user.email, WRONG_PASSWORD, ATTACKER_IP).get_data(as_text=True)

# AKUN BARU DARI ADMIN + LINK AKTIVASI

ACTIVATION_PASSWORD = "PasswordAktivasi1"
ACTIVATION_LINK_PATTERN = re.compile(r"http://localhost/auth/activate/(\S+)")


def as_client(client):
    """Semua request test berbagi 1 app context, jadi user yg login ke-cache di g. Ganti client (admin <-> pemilik
    akun) -> cache dibuang biar tiap client dibaca dari cookie-nya sendiri."""
    g.pop("_login_user", None)
    return client


def create_user(admin_client, email=NEW_EMAIL, full_name="User Baru", role=ROLE_USER_ENTRY):
    return as_client(admin_client).post("/users/new", data={"email": email, "full_name": full_name, "role": role})


def send_activation(admin_client, capsys, email=NEW_EMAIL):
    """Admin klik Send Activation Link, return token dari email yg kecetak di terminal (mode console)."""
    capsys.readouterr()
    response = as_client(admin_client).post(f"/users/{find_user(email).id}/send-activation", follow_redirects=True)
    match_list = ACTIVATION_LINK_PATTERN.findall(capsys.readouterr().out)
    return response, (match_list[-1] if match_list else None)


def activate(client, token, password=ACTIVATION_PASSWORD, confirm_password=None):
    return as_client(client).post(f"/auth/activate/{token}", data={
        "password": password, "confirm_password": confirm_password or password,
    })


def test_admin_creates_user_then_owner_activates_and_logs_in(app, admin_client, admin_user, capsys):
    """Positive: admin bikin akun (email + nama + role) -> Pending Activation, belum bisa login -> admin kirim link ->
    pemilik bikin password 2x -> akun aktif -> balik ke login -> password baru lanjut ke OTP."""
    from app.services.user_service import get_user_status

    response = create_user(admin_client)
    assert response.status_code == 302
    user = find_user(NEW_EMAIL)
    assert (user.full_name, user.role, user.is_active, user.department, user.job_title) == ("User Baru", ROLE_USER_ENTRY, False, "", "")
    assert get_user_status(user) == USER_STATUS_PENDING
    create_log = db.session.execute(db.select(AuditLog).filter_by(action=AUDIT_ACTION_CREATE, entity_id=user.id)).scalar_one()
    assert create_log.user_id == admin_user.id
    list_text = as_client(admin_client).get(response.location).get_data(as_text=True)
    assert "Pending Activation" in list_text and "Send Activation Link" in list_text

    owner_client = app.test_client()
    assert "Incorrect email or password" in post_login(as_client(owner_client), NEW_EMAIL, ACTIVATION_PASSWORD, OWNER_IP).get_data(as_text=True)

    send_response, token = send_activation(admin_client, capsys)
    assert f"Activation link sent to {NEW_EMAIL}" in send_response.get_data(as_text=True)
    assert token is not None
    page_text = as_client(owner_client).get(f"/auth/activate/{token}").get_data(as_text=True)
    assert "Set Your Password" in page_text and NEW_EMAIL in page_text

    mismatch_text = activate(owner_client, token, confirm_password="BedaSendiri123").get_data(as_text=True)
    assert "Passwords do not match" in mismatch_text
    response = activate(owner_client, token)
    assert response.status_code == 302 and "/auth/login" in response.location
    user = find_user(NEW_EMAIL)
    assert user.is_active and get_user_status(user) != USER_STATUS_PENDING
    assert db.session.scalar(db.select(db.func.count(AuditLog.id)).filter_by(
        action=AUDIT_ACTION_PASSWORD_CHANGE, entity_id=user.id)) == 1
    assert "/auth/otp" in post_login(as_client(owner_client), NEW_EMAIL, ACTIVATION_PASSWORD, OWNER_IP).location


def test_activation_link_works_once_and_new_link_replaces_old(app, admin_client, capsys, monkeypatch):
    """Negative (security): kirim ulang -> link lama mati; link yg udah dipake ga bisa dipake lagi buat ganti password."""
    create_user(admin_client)
    monkeypatch.setattr(auth_service, "OTP_RESEND_COOLDOWN_SECONDS", 0)
    _, old_token = send_activation(admin_client, capsys)
    _, new_token = send_activation(admin_client, capsys)
    assert old_token != new_token
    owner_client = app.test_client()
    old_response = as_client(owner_client).get(f"/auth/activate/{old_token}", follow_redirects=True)
    assert "invalid or has expired" in old_response.get_data(as_text=True)
    assert old_response.request.path == "/auth/login"
    assert "/auth/login" in activate(owner_client, new_token).location
    password_hash = find_user(NEW_EMAIL).password_hash
    assert "/auth/login" in activate(owner_client, new_token, password="PasswordLain999").location
    assert find_user(NEW_EMAIL).password_hash == password_hash


def test_expired_or_wrong_activation_link_rejected(app, admin_client, capsys):
    """Negative: link lewat 24 jam / token ngasal -> balik ke login, akun tetep Pending."""
    create_user(admin_client)
    _, token = send_activation(admin_client, capsys)
    db.session.execute(db.update(OtpCode).where(OtpCode.purpose == OTP_PURPOSE_ACTIVATION)
                       .values(expires_at=utc_now() - timedelta(minutes=1)))
    db.session.commit()
    owner_client = app.test_client()
    for bad_token in (token, "token-ngasal"):
        assert "/auth/login" in as_client(owner_client).get(f"/auth/activate/{bad_token}").location
        assert "/auth/login" in activate(owner_client, bad_token).location
    assert find_user(NEW_EMAIL).is_active is False


def test_activation_password_rules(app, admin_client, capsys):
    """Negative: password aktivasi ikut aturan password baru (min. 8, huruf + angka)."""
    create_user(admin_client)
    _, token = send_activation(admin_client, capsys)
    owner_client = app.test_client()
    assert "Password must contain letters and numbers" in activate(owner_client, token, password="cumahuruf").get_data(as_text=True)
    assert find_user(NEW_EMAIL).is_active is False


def test_create_user_validation(admin_client, registered_user):
    """Negative: email udah kepake, nama kosong, role ngasal -> ditolak, ga ada akun baru."""
    assert "Email is already registered" in create_user(admin_client, email=registered_user.email).get_data(as_text=True)
    assert "Name is required" in create_user(admin_client, full_name="").get_data(as_text=True)
    assert create_user(admin_client, role="superadmin").status_code == 200
    assert find_user(NEW_EMAIL) is None


def test_only_admin_can_create_user_or_send_link(logged_in_client, registered_user):
    """Negative (RBAC): user biasa ga bisa buka Create User / kirim link aktivasi."""
    assert logged_in_client.get("/users/new").status_code == 403
    assert logged_in_client.post("/users/new", data={"email": NEW_EMAIL, "full_name": "X", "role": ROLE_ADMIN}).status_code == 403
    assert logged_in_client.post(f"/users/{registered_user.id}/send-activation").status_code == 403
    assert find_user(NEW_EMAIL) is None


def test_admin_role_account_also_needs_activation(app, admin_client, capsys):
    """Positive: admin bisa bikin akun Admin; tetep Pending & tombol Send Activation Link-nya ada (walau akun admin
    lain ga bisa diubah dari panel)."""
    create_user(admin_client, role=ROLE_ADMIN)
    assert find_user(NEW_EMAIL).role == ROLE_ADMIN
    _, token = send_activation(admin_client, capsys)
    assert "/auth/login" in activate(as_client(app.test_client()), token).location
    assert find_user(NEW_EMAIL).is_active


def test_pending_account_rules(admin_client, capsys, registered_user):
    """Negative: akun Pending ga bisa diaktifin manual (belum punya password), kirim link ke akun aktif ditolak,
    kirim ulang kecepetan ditolak, lupa password diperlakuin kayak email ga terdaftar."""
    create_user(admin_client)
    user = find_user(NEW_EMAIL)
    toggle_text = as_client(admin_client).post(f"/users/{user.id}/toggle-active", follow_redirects=True).get_data(as_text=True)
    assert "send the activation link instead" in toggle_text
    assert find_user(NEW_EMAIL).is_active is False

    send_activation(admin_client, capsys)
    cooldown_response, cooldown_token = send_activation(admin_client, capsys)
    assert "Wait a moment" in cooldown_response.get_data(as_text=True) and cooldown_token is None

    active_response, _ = send_activation(admin_client, capsys, email=registered_user.email)
    assert "already activated" in active_response.get_data(as_text=True)

    capsys.readouterr()
    as_client(admin_client).post("/auth/forgot", data={"email": NEW_EMAIL})
    assert "Kode reset password ALR" not in capsys.readouterr().out


def test_pending_status_filter_and_summary(admin_client):
    """Positive: filter status Pending Activation cuma nampilin akun yg belum aktivasi, & ga diitung Inactive."""
    from app.services.user_service import build_user_summary

    create_user(admin_client)
    pending_text = as_client(admin_client).get("/users/?status=pending").get_data(as_text=True)
    inactive_text = as_client(admin_client).get("/users/?status=inactive").get_data(as_text=True)
    assert NEW_EMAIL in pending_text and NEW_EMAIL not in inactive_text
    assert build_user_summary()["inactive"] == 0


def test_smtp_failure_on_activation_link(admin_client, monkeypatch):
    """Negative: SMTP mati -> admin dapet pesan gagal, token yg ga kekirim langsung hangus."""
    from app.services import user_service

    def fail_delivery(*args):
        raise OSError("smtp mati")
    monkeypatch.setattr(user_service, "send_activation_link", fail_delivery)
    create_user(admin_client)
    response = as_client(admin_client).post(f"/users/{find_user(NEW_EMAIL).id}/send-activation", follow_redirects=True)
    assert "could not be sent" in response.get_data(as_text=True)
    assert db.session.scalar(db.select(db.func.count(OtpCode.id)).filter_by(
        purpose=OTP_PURPOSE_ACTIVATION, is_used=False)) == 0
