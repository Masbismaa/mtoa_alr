"""Test layout (sidebar, menu per role), halaman settings, dan API preferensi."""
import re

from app import create_app
from app.config import TestingConfig
from app.services.auth_service import register_user
from app.utils.constants import ROLE_ADMIN

def login_as(client, email, password, otp_code):
    """Helper: login 2 langkah."""
    client.post("/auth/login", data={"email": email, "password": password})
    client.post("/auth/otp", data={"otp_code": otp_code})

def test_dashboard_shows_topbar_profile(logged_in_client):
    """Positive: topbar nampilin nama, jabatan, departemen + preferensi dari server."""
    html_text = logged_in_client.get("/").get_data(as_text=True)
    assert "User Login" in html_text
    assert "Staff" in html_text
    assert "ICT" in html_text
    assert 'data-pref-source="server"' in html_text

def test_topbar_has_home_theme_toggle_and_user_menu(logged_in_client):
    """Topbar menyediakan Home, tombol tema, dan menu pengguna."""
    response = logged_in_client.get("/settings/")
    assert response.status_code == 200
    html_text = response.get_data(as_text=True)
    topbar_match = re.search(
        r'<header\b[^>]*class="[^"\n]*\bapp-topbar\b[^"\n]*"[^>]*>(.*?)</header>',
        html_text,
        re.DOTALL,
    )
    assert topbar_match is not None, "Header dengan class app-topbar tidak ditemukan"
    topbar_html = topbar_match.group(1)
    assert 'href="/"' in topbar_html
    assert "Home" in topbar_html
    assert "user-menu" in topbar_html
    assert "data-theme-toggle" in topbar_html

def test_user_entry_sees_locked_admin_menu(logged_in_client):
    """Negative (RBAC): user biasa liat menu Categories & Audit Logs dgn gembok, tapi ga ada link-nya."""
    html_text = logged_in_client.get("/").get_data(as_text=True)
    assert "Settings" in html_text
    assert "Groups" in html_text
    assert "Audit Logs" in html_text and 'href="/audit-logs/"' not in html_text
    assert "Categories" in html_text and 'href="/categories/"' not in html_text

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


def test_standard_dashboard_shows_personal_view_only(logged_in_client):
    """Positive: User Entry -> dashboard pribadi (panduan mulai kalau belum punya link), tanpa panel admin / akses."""
    html_text = logged_in_client.get("/").get_data(as_text=True)
    assert 'data-access-level="standard"' in html_text and "User Entry" in html_text
    assert "Get started" in html_text and "Needs Your Attention" in html_text
    assert "System Overview" not in html_text and "Admin To-Do" not in html_text and "Your Access" not in html_text


def test_sidebar_renders_inline_folders_and_opens_active_branch(logged_in_client):
    html_text = logged_in_client.get("/entries/?visibility=public").get_data(as_text=True)
    assert re.search(r'<details\b[^>]*data-sidebar-branch="section-2"[^>]*\bopen\b', html_text)
    assert re.search(r'<details\b[^>]*data-sidebar-branch="menu-link"[^>]*\bopen\b', html_text)
    assert 'class="sidebar-children sidebar-leaves"' in html_text
    assert 'aria-current="page">Public Links</a>' in html_text
    assert 'data-locked-message="You are not authorized' in html_text


def test_granted_dashboard_shows_one_panel_per_granted_access(logged_in_client, registered_user, admin_user):
    """Positive: User with access -> panel "Your Access" cuma buat akses yg dikasih; tanpa panel admin.
    Akses dicabut -> balik jadi dashboard User Entry."""
    from app.services.user_service import set_user_permissions
    from app.utils.constants import PERMISSION_MANAGE_CATEGORIES, PERMISSION_EDIT_PUBLIC_ENTRIES

    set_user_permissions(admin_user, registered_user, [PERMISSION_MANAGE_CATEGORIES, PERMISSION_EDIT_PUBLIC_ENTRIES])
    html_text = logged_in_client.get("/").get_data(as_text=True)
    assert 'data-access-level="granted"' in html_text and "User with access" in html_text
    assert 'class="card mb-3 dashboard-access"' in html_text
    assert "Manage Categories" in html_text and 'href="/categories/"' in html_text
    assert "Edit Public Links" in html_text
    assert "Open Audit Logs" not in html_text
    assert "System Overview" not in html_text and "Admin To-Do" not in html_text
    assert logged_in_client.get("/users/").status_code == 403

    set_user_permissions(admin_user, registered_user, [])
    html_text = logged_in_client.get("/").get_data(as_text=True)
    assert 'data-access-level="standard"' in html_text
    assert "Your Access" not in html_text


def test_admin_dashboard_shows_system_overview_and_admin_todo(client, admin_user, user_password, fixed_otp_code):
    """Positive: admin -> ringkasan sistem (user, monitoring) & tugas admin, bukan angka pribadi / panel akses."""
    login_as(client, admin_user.email, user_password, fixed_otp_code)
    html_text = client.get("/").get_data(as_text=True)
    assert 'data-access-level="admin"' in html_text
    assert "System Overview" in html_text and "Admin To-Do" in html_text
    assert 'href="/users/?status=locked"' in html_text and 'href="/link-monitoring/"' in html_text
    assert "Your Access" not in html_text and "Needs Your Attention" not in html_text and "Get started" not in html_text

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
    """Negative (security): belum login ga bisa nyimpen preferensi -> 401 JSON (dipanggil script, bukan redirect)."""
    response = client.post("/settings/preferences", json={"theme_mode": "dark"})
    assert response.status_code == 401
    assert response.get_json()["is_success"] is False

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
