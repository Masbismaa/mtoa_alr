"""Test halaman kelola user (khusus admin)."""
from app.services.user_service import toggle_user_active

def test_users_page_requires_login(client):
    """Negative (security): belum login dilempar ke halaman login."""
    response = client.get("/users/")
    assert response.status_code == 302
    assert "/auth/login" in response.location

def test_user_entry_cannot_open_users_page(logged_in_client):
    """Negative (RBAC): user biasa dapet 403."""
    assert logged_in_client.get("/users/").status_code == 403

def test_admin_sees_user_list(admin_client, admin_user, registered_user):
    """Positive: admin liat semua user, tanpa bocorin hash password."""
    html_text = admin_client.get("/users/").get_data(as_text=True)
    assert admin_user.email in html_text
    assert registered_user.email in html_text
    assert "Kamu" in html_text
    assert registered_user.password_hash not in html_text
    assert "argon2" not in html_text

def test_admin_filter_users(admin_client, admin_user, registered_user):
    """Positive: filter role dari URL, nilai ngaco dicuekin."""
    html_text = admin_client.get("/users/?role=user_entry").get_data(as_text=True)
    assert registered_user.email in html_text
    assert admin_user.email not in html_text.split('id="filter_keyword"')[1]
    assert admin_client.get("/users/?role=hack&status=hack&page=abc").status_code == 200

def test_admin_sidebar_users_menu_is_link(admin_client):
    """Positive: menu Users muncul di bagian Admin & bisa diklik."""
    assert 'href="/users/"' in admin_client.get("/").get_data(as_text=True)

def test_user_entry_cannot_change_role(logged_in_client, registered_user, other_user):
    """Negative (RBAC): user biasa POST langsung ke aksi admin -> 403, ga ada yg berubah."""
    assert logged_in_client.post(f"/users/{other_user.id}/role", data={"role": "admin"}).status_code == 403
    assert logged_in_client.post(f"/users/{registered_user.id}/role", data={"role": "admin"}).status_code == 403
    assert registered_user.role == "user_entry"
    assert other_user.role == "user_entry"

def test_admin_change_role_keeps_filter(admin_client, registered_user):
    """Positive: admin ganti role, balik ke tabel dgn filter yg sama."""
    response = admin_client.post(
        f"/users/{registered_user.id}/role",
        data={"role": "admin", "back_q": "user", "back_status": "active"},
    )
    assert response.status_code == 302
    assert response.location.endswith("/users/?q=user&status=active")
    assert registered_user.role == "admin"

def test_admin_cannot_deactivate_self_via_route(admin_client, admin_user):
    """Negative: nonaktifin diri sendiri ditolak + pesan error."""
    response = admin_client.post(f"/users/{admin_user.id}/toggle-active", follow_redirects=True)
    assert "tidak bisa menonaktifkan akunmu sendiri" in response.get_data(as_text=True)
    assert admin_user.is_active is True

def test_deactivated_user_logged_out_immediately(logged_in_client, admin_user, registered_user):
    """Negative (security): user yg lagi login langsung ke-logout begitu dinonaktifin."""
    assert logged_in_client.get("/").status_code == 200
    toggle_user_active(admin_user, registered_user)
    response = logged_in_client.get("/")
    assert response.status_code == 302
    assert "/auth/login" in response.location

def test_unknown_user_action_returns_404(admin_client):
    """Negative: id ngasal -> 404."""
    assert admin_client.post("/users/999/toggle-active").status_code == 404