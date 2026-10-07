"""Test halaman jelajah kategori & sub-kategori lewat route."""
from app.extensions import db
from app.models import Category
from app.services.category_service import create_sub_category, toggle_category_active

def get_category_by_name(name):
    """Helper: ambil kategori dari nama (nama di test ini unik)."""
    return db.session.execute(db.select(Category).filter_by(name=name)).scalar_one_or_none()

def test_home_shows_category_forum(logged_in_client, registered_user, category_dict):
    """Positive: Home (ringkasan) nampilin daftar kategori + sub-nya. Tabel link udah pindah ke Daftar Link."""
    create_sub_category(registered_user, category_dict["Web"], {"name": "SAP", "description": ""})
    html_text = logged_in_client.get("/").get_data(as_text=True)
    assert 'id="kategori"' in html_text
    assert 'id="daftar_link"' not in html_text
    assert "SAP" in html_text

def test_user_can_browse_category(logged_in_client, registered_user, category_dict):
    """Positive: user biasa bisa buka halaman kategori, keliatan sub-nya & breadcrumb."""
    create_sub_category(registered_user, category_dict["Web"], {"name": "SAP", "description": ""})
    html_text = logged_in_client.get(f"/categories/{category_dict['Web'].id}").get_data(as_text=True)
    assert "Sub-kategori" in html_text
    assert "SAP" in html_text
    assert "Tambah Link di sini" in html_text

def test_user_can_create_sub_via_form(logged_in_client, category_dict):
    """Positive: user biasa nambah sub lewat form."""
    response = logged_in_client.post(f"/categories/{category_dict['Web'].id}/sub/new", data={"name": "SAP", "description": ""})
    assert response.status_code == 302
    assert get_category_by_name("SAP").parent_id == category_dict["Web"].id

def test_other_user_cannot_edit_sub(client, registered_user, other_user, user_password, fixed_otp_code, category_dict):
    """Negative (RBAC): sub bikinan orang lain -> 403."""
    sap = create_sub_category(registered_user, category_dict["Web"], {"name": "SAP", "description": ""})
    client.post("/auth/login", data={"email": other_user.email, "password": user_password})
    client.post("/auth/otp", data={"otp_code": fixed_otp_code})
    assert client.post(f"/categories/{sap.id}/edit", data={"name": "Hack"}).status_code == 403
    assert client.post(f"/categories/{sap.id}/delete").status_code == 403
    assert sap.name == "SAP"

def test_inactive_category_hidden_from_user(logged_in_client, registered_user, admin_user, category_dict):
    """Negative: kategori nonaktif -> 404 buat user biasa."""
    sap = create_sub_category(registered_user, category_dict["Web"], {"name": "SAP", "description": ""})
    toggle_category_active(admin_user, sap)
    assert logged_in_client.get(f"/categories/{sap.id}").status_code == 404

def test_add_link_here_preselects_category(logged_in_client, registered_user, category_dict):
    """Positive: tombol 'Tambah Link di sini' bikin kategorinya langsung kepilih."""
    sap = create_sub_category(registered_user, category_dict["Web"], {"name": "SAP", "description": ""})
    html_text = logged_in_client.get(f"/entries/new?category_id={sap.id}").get_data(as_text=True)
    assert f'value="{sap.id}"' in html_text
    assert "Web › SAP" in html_text
    option_html = html_text.split(f'value="{sap.id}"')[1].split(">")[0]
    assert "selected" in option_html