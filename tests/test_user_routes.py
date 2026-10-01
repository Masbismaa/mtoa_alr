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

def test_user_entry_cannot_open_access_page(logged_in_client, registered_user, other_user):
    """Negative (RBAC): user biasa ga bisa buka/kirim halaman atur akses."""
    assert logged_in_client.get(f"/users/{other_user.id}/access").status_code == 403
    response = logged_in_client.post(f"/users/{registered_user.id}/access", data={"permission": ["manage_categories"]})
    assert response.status_code == 403
    assert registered_user.permission_list == []

def test_admin_grant_access_keeps_filter(admin_client, registered_user):
    """Positive: admin centang akses, balik ke tabel dgn filter yg sama."""
    page = admin_client.get(f"/users/{registered_user.id}/access?back_q=user")
    assert page.status_code == 200
    assert "Kelola kategori" in page.get_data(as_text=True)
    response = admin_client.post(
        f"/users/{registered_user.id}/access",
        data={"permission": ["manage_categories", "view_audit_logs"], "back_q": "user"},
    )
    assert response.status_code == 302
    assert response.location.endswith("/users/?q=user")
    assert sorted(permission.permission_key for permission in registered_user.permission_list) == ["manage_categories", "view_audit_logs"]

def test_access_page_for_admin_redirects(admin_client, admin_user):
    """Negative: akun admin ga punya halaman atur akses (otomatis semua akses)."""
    response = admin_client.get(f"/users/{admin_user.id}/access")
    assert response.status_code == 302
    assert response.location.endswith("/users/")

def test_role_change_route_removed(admin_client, registered_user):
    """Negative: ganti role lewat panel udah ga ada (cuma lewat command)."""
    assert admin_client.post(f"/users/{registered_user.id}/role", data={"role": "admin"}).status_code == 404
    assert registered_user.role == "user_entry"