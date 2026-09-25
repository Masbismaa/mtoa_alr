"""Fixture Pytest yang dipakai bersama oleh semua file test."""
import pytest

from app import create_app
from app.extensions import db
from app.services import auth_service

# data login yg dipake bareng di banyak test
USER_PASSWORD = "PasswordKuat123"
FIXED_OTP_CODE = "123456"


@pytest.fixture()
def app():
    """Membuat aplikasi testing + tabel di SQLite memori; dibersihkan setelah tiap test."""
    app = create_app("testing")
    with app.app_context():
        # Setup: buat semua tabel kosong
        db.create_all()
        yield app
        # Teardown: tutup session & hapus semua tabel
        db.session.remove()
        db.drop_all()

@pytest.fixture()
def client(app):
    """Membuat test client untuk mensimulasikan request HTTP ke aplikasi."""
    return app.test_client()

@pytest.fixture()
def user_password():
    """Password contoh yg valid."""
    return USER_PASSWORD

@pytest.fixture()
def registered_user(app):
    """User yg udah terdaftar, siap dipake login."""
    return auth_service.register_user(
        email="user.login@spindo.com",
        password=USER_PASSWORD,
        full_name="User Login",
        department="ICT",
        job_title="Staff",
    )

@pytest.fixture()
def fixed_otp_code(monkeypatch):
    """Bikin OTP selalu 123456 biar test bisa nebak kodenya."""
    monkeypatch.setattr(auth_service, "generate_otp_code", lambda: FIXED_OTP_CODE)
    return FIXED_OTP_CODE

@pytest.fixture()
def logged_in_client(client, registered_user, fixed_otp_code):
    """Client yg udah login sebagai registered_user (lewat password + OTP)."""
    client.post("/auth/login", data={"email": registered_user.email, "password": USER_PASSWORD})
    client.post("/auth/otp", data={"otp_code": fixed_otp_code})
    return client