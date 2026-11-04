"""Test login & bikin user cukup isi nama depan email, domain kantor dilengkapi otomatis."""
from app.extensions import db
from app.models import User
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

def test_create_user_with_local_part(admin_client):
    """Positive: admin cukup isi nama depan -> akun kesimpen pake email lengkap."""
    response = admin_client.post("/users/new", data={"email": "budi.santoso", "full_name": "Budi Santoso", "role": "user_entry"})
    assert response.status_code == 302
    assert db.session.execute(db.select(User).filter_by(email="budi.santoso@spindo.com")).scalar_one_or_none() is not None

def test_create_user_other_domain_rejected(admin_client):
    """Negative (security): ketik lengkap pake domain lain tetep ditolak."""
    response = admin_client.post("/users/new", data={"email": "budi@gmail.com", "full_name": "Budi", "role": "user_entry"})
    assert response.status_code == 200
    assert "Email must use the @spindo.com domain" in response.get_data(as_text=True)
    assert db.session.execute(db.select(User).filter_by(email="budi@gmail.com")).scalar_one_or_none() is None

def test_login_with_local_part(client, registered_user, user_password, fixed_otp_code):
    """Positive: login cukup isi nama depan -> lanjut ke halaman OTP."""
    response = client.post("/auth/login", data={"email": "user.login", "password": user_password})
    assert response.status_code == 302
    assert "/auth/otp" in response.location
