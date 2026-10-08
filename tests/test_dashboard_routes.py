"""Test halaman Daftar Link (search, filter, copy, truncate, pagination) + Dashboard yg sekarang cuma ringkasan."""
from app.services import entry_table_service
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
    html_text = logged_in_client.get("/entries/?q=router").get_data(as_text=True)
    assert "Router Lantai 2" in html_text
    assert "Portal HR" not in html_text

def test_dashboard_category_filter(logged_in_client, registered_user, category_dict):
    """Positive: filter kategori dari URL."""
    create_access_entry(registered_user, build_entry_dict(category_dict["Web"], "Portal HR", "https://hr.spindo.com"))
    create_access_entry(registered_user, build_entry_dict(
        category_dict["Network"], "Switch Core", "", address="10.0.0.2", port="22",
    ))
    html_text = logged_in_client.get(f"/entries/?category_id={category_dict['Network'].id}").get_data(as_text=True)
    # cek tabel Daftar Link aja, daftar kategori di atasnya emang nampilin link terbaru tiap kategori
    table_html = html_text.split('id="daftar_link"')[1]
    assert "Switch Core" in table_html
    assert "Portal HR" not in table_html

def test_dashboard_ignores_invalid_params(logged_in_client, category_dict):
    """Negative: parameter ngaco ga bikin error."""
    response = logged_in_client.get("/entries/?page=abc&category_id=xyz&visibility=hack")
    assert response.status_code == 200

def test_dashboard_has_copy_button(logged_in_client, registered_user, category_dict, read_entry_table):
    """Positive: kolom URL / Address (yg ada tombol copy-nya) bawa URL lengkap."""
    create_access_entry(registered_user, build_entry_dict(category_dict["Web"], "Portal HR", "https://hr.spindo.com"))
    payload = read_entry_table(logged_in_client, "/entries/?run=1")
    assert payload["rows"][0]["access_text"] == "https://hr.spindo.com"

def test_dashboard_truncates_long_description(logged_in_client, registered_user, category_dict, read_entry_table):
    """Positive: deskripsi panjang dikirim utuh (buat tooltip), motongnya di tampilan React (dites di columns.test.jsx)."""
    long_text = "A" * 200
    create_access_entry(registered_user, build_entry_dict(
        category_dict["Web"], "Portal HR", "https://hr.spindo.com", description=long_text,
    ))
    payload = read_entry_table(logged_in_client, "/entries/?run=1")
    assert payload["rows"][0]["description"] == long_text

def test_dashboard_empty_search_result(logged_in_client, category_dict):
    """Positive: pencarian kosong nampilin pesan + tombol reset."""
    html_text = logged_in_client.get("/entries/?q=zzzz").get_data(as_text=True)
    assert "Tidak ada hasil" in html_text
    assert "Reset filter" in html_text

def test_pagination_link_keeps_filter(logged_in_client, registered_user, category_dict, monkeypatch, read_entry_table):
    """Positive: ada halaman berikutnya & kriteria yg dibawa ke halaman itu tetep ada filternya."""
    monkeypatch.setattr(entry_table_service, "PER_PAGE", 1)
    web = category_dict["Web"]
    create_access_entry(registered_user, build_entry_dict(web, "Link A", "https://a.spindo.com"))
    create_access_entry(registered_user, build_entry_dict(web, "Link B", "https://b.spindo.com"))
    payload = read_entry_table(logged_in_client, f"/entries/?category_id={web.id}")
    assert payload["pages"] == 2 and payload["page_list"] == [1, 2]
    assert payload["query"] == {"run": ["1"], "category_id": [str(web.id)]}

def test_dashboard_is_summary_only(logged_in_client, registered_user, category_dict):
    """Positive: Dashboard cuma ringkasan seluruh data (ga ada tabel & kriteria), ada jalan ke Daftar Link."""
    create_access_entry(registered_user, build_entry_dict(category_dict["Web"], "Portal HR", "https://hr.spindo.com"))
    html_text = logged_in_client.get("/").get_data(as_text=True)
    assert 'id="daftar_link"' not in html_text and "data-selection-form" not in html_text
    assert 'href="/entries/"' in html_text

def test_dashboard_old_filter_url_redirects(logged_in_client):
    """Positive: link lama /?q=... dilempar ke Daftar Link + kriterianya tetep, langsung ke tabel."""
    response = logged_in_client.get("/?q=router&visibility=public")
    assert response.status_code == 302
    assert response.location.endswith("/entries/?q=router&visibility=public#daftar_link")

def test_entry_list_heading_shows_scope(logged_in_client, registered_user, category_dict):
    """Positive: judul tabel bedain seluruh data vs hasil pencarian."""
    create_access_entry(registered_user, build_entry_dict(category_dict["Web"], "Portal HR", "https://hr.spindo.com"))
    assert "Seluruh link: 1 data" in logged_in_client.get("/entries/?run=1").get_data(as_text=True)
    assert "Hasil pencarian: 0 data" in logged_in_client.get("/entries/?q=zzzz").get_data(as_text=True)
