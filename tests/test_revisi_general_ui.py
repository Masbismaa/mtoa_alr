"""Test revisi: General tanpa username/access note, label mode tampilan, maks 10 field, pagination 10, default APP_ENV."""
from datetime import datetime, timezone
from app import resolve_config_name
from app.services.access_entry_service import create_access_entry, search_visible_entries
from app.utils.constants import CUSTOM_FIELD_MAX_COUNT, PER_PAGE, VISIBILITY_PRIVATE
from app.utils.datetime_helper import format_local_datetime

def build_entry_dict(category, title, **override_dict):
    """Helper: data link contoh."""
    entry_dict = {
        "category_id": category.id, "title": title, "url": "https://hr.spindo.com",
        "address": "", "port": "", "username": "", "access_note": "", "description": "",
        "visibility": VISIBILITY_PRIVATE,
    }
    entry_dict.update(override_dict)
    return entry_dict

def test_general_entry_drops_credential(app, registered_user, category_dict):
    """Negative: username & access note yg dikirim paksa ke kategori General ga disimpen."""
    entry = create_access_entry(
        registered_user,
        build_entry_dict(category_dict["General"], "Panduan VPN", username="admin", access_note="rahasia"),
        [("Langkah", "<p>Buka aplikasi VPN</p>")],
    )
    assert entry.username is None
    assert entry.encrypted_access_note is None

def test_web_entry_keeps_credential(app, registered_user, category_dict):
    """Positive: kategori selain General tetep nyimpen username & access note."""
    entry = create_access_entry(registered_user, build_entry_dict(category_dict["Web"], "Portal HR", username="admin", access_note="rahasia"))
    assert entry.username == "admin"
    assert entry.encrypted_access_note is not None

def test_general_form_hides_credential(logged_in_client, category_dict):
    """Positive: form kategori General nyembunyiin kolom Username & Access Note dari awal."""
    html_text = logged_in_client.get(f"/entries/new?category_id={category_dict['General'].id}").get_data(as_text=True)
    assert 'data-has-credential-field="false"' in html_text
    assert "<div data-credential-field hidden>" in html_text

def test_custom_field_max_is_ten():
    """Positive: batas field tambahan General 10."""
    assert CUSTOM_FIELD_MAX_COUNT == 10

def test_pagination_is_ten(app, registered_user, category_dict):
    """Positive: semua tabel 10 baris per halaman."""
    for index in range(PER_PAGE + 1):
        create_access_entry(registered_user, build_entry_dict(category_dict["Web"], f"Link {index}", url=f"https://link{index}.spindo.com"))
    assert PER_PAGE == 10
    assert len(search_visible_entries(registered_user).items) == 10

def test_theme_toggle_shows_mode_text(logged_in_client):
    """Positive: tombol tema ada tulisan Dark mode / Light mode."""
    html_text = logged_in_client.get("/").get_data(as_text=True)
    assert "Dark mode" in html_text
    assert "Light mode" in html_text

def test_page_title_has_single_suffix(logged_in_client):
    """Positive: judul tab browser cuma sekali '- ALR', tanpa MTOA."""
    html_text = logged_in_client.get("/").get_data(as_text=True)
    assert "<title>Dashboard - ALR</title>" in html_text
    assert "MTOA" not in html_text

def test_local_datetime_uses_indonesian_month():
    """Positive: bulan tampil versi Indonesia, sama kayak di Excel."""
    assert format_local_datetime(datetime(2026, 10, 5, 3, 7, tzinfo=timezone.utc)) == "05 Okt 2026, 10:07 WIB"

def test_app_env_defaults_to_production(monkeypatch):
    """Negative (security): APP_ENV lupa diisi -> dianggap production, bukan development."""
    monkeypatch.delenv("APP_ENV", raising=False)
    assert resolve_config_name() == "production"
    monkeypatch.setenv("APP_ENV", "development")
    assert resolve_config_name() == "development"
    assert resolve_config_name("testing") == "testing"
