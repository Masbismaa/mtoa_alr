"""Test halaman kelola kategori (khusus admin)."""
from app.extensions import db
from app.models import Category
from app.services.category_service import create_category

def get_category_by_name(name):
    """Helper: ambil kategori dari nama."""
    return db.session.execute(db.select(Category).filter_by(name=name)).scalar_one_or_none()

def test_categories_require_login(client):
    """Negative (security): belum login dilempar ke halaman login."""
    response = client.get("/categories/")
    assert response.status_code == 302
    assert "/auth/login" in response.location

def test_user_entry_cannot_open_categories(logged_in_client, category_dict):
    """Negative (RBAC): user biasa dapet 403, termasuk lewat POST langsung."""
    assert logged_in_client.get("/categories/").status_code == 403
    assert logged_in_client.post("/categories/new", data={"name": "Hack"}).status_code == 403
    assert get_category_by_name("Hack") is None

def test_admin_sees_category_table(admin_client, category_dict):
    """Positive: admin liat semua kategori + tanda bawaan."""
    html_text = admin_client.get("/categories/").get_data(as_text=True)
    for name in ["Web", "Application", "Network", "General"]:
        assert name in html_text
    assert "Bawaan" in html_text

def test_admin_sidebar_category_menu_is_link(admin_client, category_dict):
    """Positive: menu Categories udah bisa diklik (bukan 'Segera' lagi)."""
    assert 'href="/categories/"' in admin_client.get("/").get_data(as_text=True)

def test_admin_create_category(admin_client, category_dict):
    """Positive: tambah kategori lewat form."""
    response = admin_client.post("/categories/new", data={"name": "Database", "description": "Server DB"})
    assert response.status_code == 302
    assert get_category_by_name("Database") is not None

def test_admin_create_duplicate_shows_error(admin_client, category_dict):
    """Negative: nama dobel balik ke form + pesan error."""
    response = admin_client.post("/categories/new", data={"name": "WEB", "description": ""})
    assert response.status_code == 200
    assert "sudah ada" in response.get_data(as_text=True)

def test_admin_toggle_category(admin_client, admin_user, category_dict):
    """Positive: nonaktifin kategori, ilang dari form tambah link."""
    category = create_category(admin_user, {"name": "Printer", "description": ""})
    # follow_redirects biar flash "Printer dinonaktifkan" kebaca di halaman ini, ga kebawa ke form link
    admin_client.post(f"/categories/{category.id}/toggle", follow_redirects=True)
    assert category.is_active is False
    assert "Printer" not in admin_client.get("/entries/new").get_data(as_text=True)

def test_admin_delete_default_category_blocked(admin_client, category_dict):
    """Negative: hapus kategori bawaan ditolak, datanya tetep ada."""
    response = admin_client.post(f"/categories/{category_dict['Web'].id}/delete", follow_redirects=True)
    assert "tidak bisa dihapus" in response.get_data(as_text=True)
    assert get_category_by_name("Web") is not None

def test_unknown_category_returns_404(admin_client):
    """Negative: id ngasal -> 404."""
    assert admin_client.get("/categories/999/edit").status_code == 404