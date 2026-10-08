"""Test login & daftar cukup isi nama depan email, domain kantor dilengkapi otomatis."""
from app.extensions import db
from app.models import PendingRegistration, User
from app.utils.text_helper import complete_email

def test_complete_email_adds_domain():
    """Positive: nama depan aja -> dilengkapi domain, dirapihin huruf kecil & spasi."""
    assert complete_email("  Budi.Santoso ", "spindo.com") == "budi.santoso@spindo.com"

def test_complete_email_keeps_full_email():
    """Positive: yg udah ketik lengkap (atau paste) dibiarin, domain lain tetep ditolak service nanti."""
    assert complete_email("budi@spindo.com", "spindo.com") == "budi@spindo.com"
    assert complete_email("budi@gmail.com", "spindo.com") == "budi@gmail.com"

def test_complete_email_empty_stays_empty():
    """Negative: kosong tetep kosong biar pesan 'Email wajib diisi' muncul."""
    assert complete_email("", "spindo.com") == ""
    assert complete_email(None, "spindo.com") == ""

def test_login_page_shows_domain(client):
    """Positive: domain kantor tampil nempel di kanan isian email."""
    assert "@spindo.com</span>" in client.get("/auth/login").get_data(as_text=True)

def test_register_with_local_part(client, user_password):
    """Positive: daftar cukup isi nama depan -> pendaftaran kesimpen pake email lengkap."""
    response = client.post("/auth/register", data={
        "email": "budi.santoso", "full_name": "Budi Santoso", "department": "ICT", "job_title": "Staff",
        "password": user_password, "confirm_password": user_password,
    })
    assert response.status_code == 302
    assert db.session.execute(db.select(PendingRegistration).filter_by(email="budi.santoso@spindo.com")).scalar_one_or_none() is not None

def test_register_other_domain_rejected(client, user_password):
    """Negative (security): ketik lengkap pake domain lain tetep ditolak."""
    response = client.post("/auth/register", data={
        "email": "budi@gmail.com", "full_name": "Budi", "department": "ICT", "job_title": "Staff",
        "password": user_password, "confirm_password": user_password,
    })
    assert response.status_code == 200
    assert db.session.execute(db.select(PendingRegistration).filter_by(email="budi@gmail.com")).scalar_one_or_none() is None

def test_login_with_local_part(client, registered_user, user_password, fixed_otp_code):
    """Positive: login cukup isi nama depan -> lanjut ke halaman OTP."""
    response = client.post("/auth/login", data={"email": "user.login", "password": user_password})
    assert response.status_code == 302
    assert "/auth/otp" in response.location
