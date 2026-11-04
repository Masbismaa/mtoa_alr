"""Test halaman kelola kategori (khusus admin)."""
from app.extensions import db
from app.models import Category
from app.services.category_service import create_sub_category

def get_category_by_name(name):
    """Helper: ambil kategori dari nama."""
    return db.session.execute(db.select(Category).filter_by(name=name)).scalar_one_or_none()

def test_categories_require_login(client):
    """Negative (security): belum login dilempar ke halaman login."""
    response = client.get("/categories/")
    assert response.status_code == 302
    assert "/auth/login" in response.location

def test_user_manages_own_categories_on_category_page(logged_in_client, registered_user, other_user, category_dict):
    """Positive + negative (RBAC): user biasa buka halaman kelola kategori, cuma liat sub bikinannya sendiri
    (Edit, Deactivate, Delete), kategori bawaan ga bisa diubah, sub orang lain ga keliatan & ga bisa diubah."""
    web = category_dict["Web"]
    sap = create_sub_category(registered_user, web, {"name": "SAP", "description": ""})
    other_sap = create_sub_category(other_user, web, {"name": "SAP Orang", "description": ""})
    html_text = logged_in_client.get("/categories/").get_data(as_text=True)
    assert "SAP" in html_text and "SAP Orang" not in html_text
    assert f"/categories/{sap.id}/edit" in html_text and f"/categories/{sap.id}/delete" in html_text
    assert f"/categories/{web.id}/edit" not in html_text
    assert logged_in_client.post(f"/categories/{web.id}/toggle").status_code == 403
    assert logged_in_client.post(f"/categories/{other_sap.id}/toggle").status_code == 403
    logged_in_client.post(f"/categories/{sap.id}/toggle")
    assert sap.is_active is False

def test_admin_sees_category_table(admin_client, category_dict):
    """Positive: admin liat semua kategori + tanda bawaan."""
    html_text = admin_client.get("/categories/").get_data(as_text=True)
    for name in ["Web", "Application", "Network", "General"]:
        assert name in html_text
    assert "Built-in" in html_text

def test_admin_sidebar_category_menu_is_link(admin_client, category_dict):
    """Positive: menu Categories udah bisa diklik (bukan 'Segera' lagi)."""
    assert 'href="/categories/"' in admin_client.get("/").get_data(as_text=True)

def test_user_adds_private_main_category(logged_in_client, other_user, category_dict):
    """Positive + negative: user biasa nambah kategori utama sendiri lewat form (bisa dibuka & dikelola),
    kategori utama pribadi orang lain ga keliatan & ga bisa dibuka."""
    assert "Add Main Category" in logged_in_client.get("/categories/").get_data(as_text=True)
    response = logged_in_client.post("/categories/new", data={"name": "Database", "description": "Server DB"})
    assert response.status_code == 302
    database = get_category_by_name("Database")
    assert database is not None and database.parent_id is None
    html_text = logged_in_client.get("/categories/").get_data(as_text=True)
    assert "Database" in html_text and f"/categories/{database.id}/edit" in html_text
    assert logged_in_client.get(f"/categories/{database.id}").status_code == 200
    from app.services.category_service import create_category
    other_main = create_category(other_user, {"name": "Punya Orang", "description": ""})
    assert "Punya Orang" not in logged_in_client.get("/categories/").get_data(as_text=True)
    assert logged_in_client.get(f"/categories/{other_main.id}").status_code == 404
    assert logged_in_client.post(f"/categories/{other_main.id}/toggle").status_code == 403

def test_create_main_category_same_as_builtin_shows_error(logged_in_client, category_dict):
    """Negative: kategori utama ga boleh kembar sama kategori bawaan (beda huruf besar/kecil tetep ditolak)."""
    response = logged_in_client.post("/categories/new", data={"name": "WEB", "description": ""})
    assert response.status_code == 200
    assert "already exists" in response.get_data(as_text=True)

def test_create_duplicate_sub_shows_error(admin_client, category_dict):
    """Negative: nama sub dobel (beda huruf besar/kecil) balik ke form + pesan error."""
    url = f"/categories/{category_dict['Web'].id}/sub/new"
    assert admin_client.post(url, data={"name": "SAP", "description": ""}).status_code == 302
    response = admin_client.post(url, data={"name": "sap", "description": ""})
    assert response.status_code == 200
    assert "already exists" in response.get_data(as_text=True)

def test_admin_toggle_category(admin_client, admin_user, category_dict):
    """Positive: nonaktifin kategori, ilang dari form tambah link."""
    category = create_sub_category(admin_user, category_dict["Network"], {"name": "Printer", "description": ""})
    # follow_redirects biar flash "Printer dinonaktifkan" kebaca di halaman ini, ga kebawa ke form link
    admin_client.post(f"/categories/{category.id}/toggle", follow_redirects=True)
    assert category.is_active is False
    assert "Printer" not in admin_client.get("/entries/new").get_data(as_text=True)

def test_admin_delete_default_category_blocked(admin_client, category_dict):
    """Negative: hapus kategori bawaan ditolak, datanya tetep ada."""
    response = admin_client.post(f"/categories/{category_dict['Web'].id}/delete", follow_redirects=True)
    assert "be deleted" in response.get_data(as_text=True)
    assert get_category_by_name("Web") is not None

def test_unknown_category_returns_404(admin_client):
    """Negative: id ngasal -> 404."""
    assert admin_client.get("/categories/999/edit").status_code == 404