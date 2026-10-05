"""Test halaman dashboard: search, filter, copy, truncate, pagination."""
from app.routes import main_routes
from app.services.access_entry_service import create_access_entry
from app.utils.constants import VISIBILITY_PRIVATE

def build_entry_dict(category, title, url, **override_dict):
    """Helper: data link contoh."""
    entry_dict = {
        "category_id": category.id, "title": title, "url": url,
        "address": "", "port": "", "username": "", "access_note": "", "description": "",
        "visibility": VISIBILITY_PRIVATE,
    }
    entry_dict.update(override_dict)
    return entry_dict

def test_dashboard_search_filters_table(logged_in_client, registered_user, category_dict):
    """Positive: cuma data yg cocok yg tampil."""
    web = category_dict["Web"]
    create_access_entry(registered_user, build_entry_dict(web, "Portal HR", "https://hr.spindo.com"))
    create_access_entry(registered_user, build_entry_dict(web, "Router Lantai 2", "https://router.spindo.com"))
    html_text = logged_in_client.get("/?q=router").get_data(as_text=True)
    assert "Router Lantai 2" in html_text
    assert "Portal HR" not in html_text

def test_dashboard_category_filter(logged_in_client, registered_user, category_dict):
    """Positive: filter kategori dari URL."""
    create_access_entry(registered_user, build_entry_dict(category_dict["Web"], "Portal HR", "https://hr.spindo.com"))
    create_access_entry(registered_user, build_entry_dict(
        category_dict["Network"], "Switch Core", "", address="10.0.0.2", port="22",
    ))
    html_text = logged_in_client.get(f"/?category_id={category_dict['Network'].id}").get_data(as_text=True)
    # cek tabel Daftar Link aja, daftar kategori di atasnya emang nampilin link terbaru tiap kategori
    table_html = html_text.split('id="daftar_link"')[1]
    assert "Switch Core" in table_html
    assert "Portal HR" not in table_html

def test_dashboard_ignores_invalid_params(logged_in_client, category_dict):
    """Negative: parameter ngaco ga bikin error."""
    response = logged_in_client.get("/?page=abc&category_id=xyz&visibility=hack")
    assert response.status_code == 200

def test_dashboard_has_copy_button(logged_in_client, registered_user, category_dict):
    """Positive: tombol copy di tabel bawa URL lengkap."""
    create_access_entry(registered_user, build_entry_dict(category_dict["Web"], "Portal HR", "https://hr.spindo.com"))
    html_text = logged_in_client.get("/").get_data(as_text=True)
    assert 'data-copy-text="https://hr.spindo.com"' in html_text

def test_dashboard_truncates_long_description(logged_in_client, registered_user, category_dict):
    """Positive: deskripsi panjang dipotong, teks lengkap ada di tooltip."""
    long_text = "A" * 200
    create_access_entry(registered_user, build_entry_dict(
        category_dict["Web"], "Portal HR", "https://hr.spindo.com", description=long_text,
    ))
    html_text = logged_in_client.get("/").get_data(as_text=True)
    assert "A" * 59 + "…" in html_text
    assert f'title="{long_text}"' in html_text

def test_dashboard_empty_search_result(logged_in_client, category_dict):
    """Positive: pencarian kosong nampilin pesan + tombol reset."""
    html_text = logged_in_client.get("/?q=zzzz").get_data(as_text=True)
    assert "Tidak ada hasil" in html_text
    assert "Reset filter" in html_text

def test_pagination_link_keeps_filter(logged_in_client, registered_user, category_dict, monkeypatch):
    """Positive: link halaman berikutnya tetep bawa filter."""
    monkeypatch.setattr(main_routes, "PER_PAGE", 1)
    web = category_dict["Web"]
    create_access_entry(registered_user, build_entry_dict(web, "Link A", "https://a.spindo.com"))
    create_access_entry(registered_user, build_entry_dict(web, "Link B", "https://b.spindo.com"))
    html_text = logged_in_client.get(f"/?category_id={web.id}").get_data(as_text=True)
    assert "page=2" in html_text
    assert f"category_id={web.id}" in html_text