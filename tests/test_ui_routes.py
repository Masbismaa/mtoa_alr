"""Test layout (sidebar, menu per role), halaman settings, dan API preferensi."""
from app import create_app
from app.config import TestingConfig
from app.services.auth_service import register_user
from app.utils.constants import ROLE_ADMIN

def login_as(client, email, password, otp_code):
    """Helper: login 2 langkah."""
    client.post("/auth/login", data={"email": email, "password": password})
    client.post("/auth/otp", data={"otp_code": otp_code})

def test_dashboard_shows_sidebar_profile(logged_in_client):
    """Positive: sidebar nampilin nama, jabatan, departemen + preferensi dari server."""
    html_text = logged_in_client.get("/").get_data(as_text=True)
    assert "User Login" in html_text
    assert "Staff" in html_text
    assert "ICT" in html_text
    assert 'data-pref-source="server"' in html_text

def test_user_entry_does_not_see_admin_menu(logged_in_client):
    """Negative (RBAC): user biasa ga liat menu Categories & Audit Logs."""
    html_text = logged_in_client.get("/").get_data(as_text=True)
    assert "Settings" in html_text
    assert "Groups" in html_text
    assert "Audit Logs" not in html_text
    assert "Categories" not in html_text

def test_admin_sees_admin_menu(client, user_password, fixed_otp_code):
    """Positive (RBAC): admin liat menu Categories & Audit Logs."""
    register_user(
        email="admin.ui@spindo.com", password=user_password, full_name="Admin UI",
        department="ICT", job_title="Manager", role=ROLE_ADMIN,
    )
    login_as(client, "admin.ui@spindo.com", user_password, fixed_otp_code)
    html_text = client.get("/").get_data(as_text=True)
    assert "Audit Logs" in html_text
    assert "Categories" in html_text

def test_settings_page_loads(logged_in_client, registered_user):
    """Positive: halaman settings nampilin profil lengkap."""
    response = logged_in_client.get("/settings/")
    assert response.status_code == 200
    assert registered_user.email in response.get_data(as_text=True)

def test_update_preference_via_api(logged_in_client):
    """Positive: API simpen preferensi balikin format response standar."""
    response = logged_in_client.post("/settings/preferences", json={"theme_mode": "dark"})
    body_dict = response.get_json()
    assert response.status_code == 200
    assert body_dict["is_success"] is True
    assert body_dict["data"]["theme_mode"] == "dark"

def test_saved_theme_applied_to_html(logged_in_client):
    """Positive: tema yg disimpen langsung kepasang di <html> pas halaman dibuka."""
    logged_in_client.post("/settings/preferences", json={"theme_mode": "dark", "accent_color": "#ff6b9d"})
    html_text = logged_in_client.get("/").get_data(as_text=True)
    assert 'data-theme="dark"' in html_text
    assert 'data-accent="pink"' in html_text

def test_update_preference_invalid_value_returns_400(logged_in_client):
    """Negative: nilai ngasal ditolak + dikasih tau field mana yg salah."""
    response = logged_in_client.post("/settings/preferences", json={"theme_mode": "neon"})
    assert response.status_code == 400
    assert response.get_json()["error_list"][0]["field"] == "theme_mode"

def test_update_preference_non_json_returns_400(logged_in_client):
    """Negative: body bukan JSON ditolak."""
    response = logged_in_client.post("/settings/preferences", data="bukan json", content_type="text/plain")
    assert response.status_code == 400

def test_update_preference_requires_login(client):
    """Negative (security): belum login ga bisa nyimpen preferensi."""
    response = client.post("/settings/preferences", json={"theme_mode": "dark"})
    assert response.status_code == 302
    assert "/auth/login" in response.location

def test_preference_api_rejects_missing_csrf_token(monkeypatch):
    """Negative (security): CSRF nyala -> request tanpa token ditolak."""
    monkeypatch.setattr(TestingConfig, "WTF_CSRF_ENABLED", True)
    csrf_client = create_app("testing").test_client()
    response = csrf_client.post("/settings/preferences", json={"theme_mode": "dark"})
    assert response.status_code == 400

def test_auth_page_uses_local_preference(client):
    """Positive: halaman login (belum login) pake preferensi dari localStorage."""
    html_text = client.get("/auth/login").get_data(as_text=True)
    assert 'data-pref-source="local"' in html_text
    assert "data-theme-toggle" in html_text