"""Test halaman kelola user (khusus admin)."""
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