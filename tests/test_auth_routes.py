"""Test halaman register, login 2 langkah (password -> OTP), logout, dan rate limit."""
from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import User
from app.utils.constants import LOGIN_MAX_FAILED_COUNT

def build_register_form_dict(confirm_password="PasswordKuat123"):
    """Helper: isi form register."""
    return {
        "email": "baru@spindo.com",
        "full_name": "User Baru",
        "department": "ICT",
        "job_title": "Staff",
        "password": "PasswordKuat123",
        "confirm_password": confirm_password,
    }

def login_with_otp(client, email, password, otp_code):
    """Helper: jalanin login langkah 1 + 2."""
    login_response = client.post("/auth/login", data={"email": email, "password": password})
    otp_response = client.post("/auth/otp", data={"otp_code": otp_code})
    return login_response, otp_response

def test_home_requires_login(client):
    """beranda ga bisa dibuka tanpa login."""
    response = client.get("/")
    assert response.status_code == 302
    assert "/auth/login" in response.location

def test_register_page_loads(client):
    """halaman register kebuka."""
    response = client.get("/auth/register")
    assert response.status_code == 200
    assert "Daftar Akun" in response.get_data(as_text=True)

def test_register_post_creates_user(client):
    """daftar sukses -> diarahkan ke login & user kesimpen."""
    response = client.post("/auth/register", data=build_register_form_dict())
    assert response.status_code == 302
    assert "/auth/login" in response.location
    user = db.session.execute(db.select(User).filter_by(email="baru@spindo.com")).scalar_one_or_none()
    assert user is not None

def test_register_password_mismatch(client):
    """konfirmasi password beda -> tetep di halaman register + pesan error."""
    response = client.post("/auth/register", data=build_register_form_dict(confirm_password="BedaSendiri123"))
    assert response.status_code == 200
    assert "Konfirmasi password tidak sama" in response.get_data(as_text=True)

def test_full_login_flow(client, registered_user, user_password, fixed_otp_code):
    """login -> Next ke halaman OTP -> isi OTP -> masuk beranda."""
    login_response = client.post("/auth/login", data={"email": registered_user.email, "password": user_password})
    assert login_response.status_code == 302
    assert "/auth/otp" in login_response.location

    otp_page = client.get("/auth/otp")
    assert otp_page.status_code == 200
    assert "us********@spindo.com" in otp_page.get_data(as_text=True)

    otp_response = client.post("/auth/otp", data={"otp_code": fixed_otp_code})
    assert otp_response.status_code == 302

    home_response = client.get("/")
    assert home_response.status_code == 200
    assert "User Login" in home_response.get_data(as_text=True)

def test_login_wrong_password_shows_generic_error(client, registered_user):
    """password salah -> tetep di halaman login + pesan umum."""
    response = client.post("/auth/login", data={"email": registered_user.email, "password": "PasswordSalah1"})
    assert response.status_code == 200
    assert "Email atau password salah" in response.get_data(as_text=True)

def test_otp_page_without_login_step(client):
    """halaman OTP ga bisa dibuka langsung tanpa lewat langkah 1."""
    response = client.get("/auth/otp")
    assert response.status_code == 302
    assert "/auth/login" in response.location

def test_logout(client, registered_user, user_password, fixed_otp_code):
    """abis logout, beranda ga bisa dibuka lagi."""
    login_with_otp(client, registered_user.email, user_password, fixed_otp_code)
    logout_response = client.post("/auth/logout")
    assert logout_response.status_code == 302
    assert "/auth/login" in client.get("/").location

def test_login_rate_limit_returns_429(monkeypatch):
    """lebih dari 10x POST login per menit -> diblok (429)."""
    monkeypatch.setattr(TestingConfig, "RATELIMIT_ENABLED", True)
    limited_client = create_app("testing").test_client()
    status_code_list = [limited_client.post("/auth/login", data={}).status_code for _ in range(11)]
    assert status_code_list[:10] == [200] * 10
    assert status_code_list[10] == 429

def test_locked_during_otp_goes_back_to_login(client, registered_user, user_password, fixed_otp_code):
    """Negative (security): akun kekunci di langkah OTP -> sesi OTP diputus, balik ke login."""
    client.post("/auth/login", data={"email": registered_user.email, "password": user_password})
    for _ in range(LOGIN_MAX_FAILED_COUNT - 1):
        client.post("/auth/otp", data={"otp_code": "000000"})
    response = client.post("/auth/otp", data={"otp_code": "000000"})
    assert response.status_code == 302
    assert "/auth/login" in response.location
    assert "/auth/login" in client.get("/auth/otp").location