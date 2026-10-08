"""Test tabel ala ALV: urutan kolom (?sort=), layout kolom per akun, hasil pencarian langsung ke tabel, balik dari detail bawa filter."""
import pytest
from werkzeug.datastructures import MultiDict
from app import create_app
from app.config import TestingConfig
from app.services.access_entry_service import create_access_entry, list_visible_entries_for_export
from app.services.audit_service import log_audit
from app.utils.constants import AUDIT_ACTION_LOGIN_FAILED, PER_PAGE, VISIBILITY_PRIVATE
from app.utils.data_table import SortOption, build_table_view, read_sort
from app.schemas.table_schema import ENTRY_COLUMN_LIST, TABLE_ENTRY
from app.utils.url_helper import get_safe_back_url

LAYOUT_URL = "/settings/table-layout"

def create_entry(user, category, title):
    """Helper: bikin link contoh (private)."""
    return create_access_entry(user, {
        "category_id": category.id, "title": title, "url": f"https://{title.lower().replace(' ', '-')}.spindo.com",
        "address": "", "port": "", "username": "", "access_note": "", "description": "", "visibility": VISIBILITY_PRIVATE,
    })

def get_card_html(client, url, card_id):
    """Helper: isi kartu tabel aja (bagian lain halaman ga ikut dicek)."""
    html_text = client.get(url).get_data(as_text=True)
    return html_text.split(f'id="{card_id}"')[1].split('class="card-footer')[0]

def assert_order(html_text, text_list):
    """Helper: teks muncul berurutan di HTML."""
    position_list = [html_text.index(text) for text in text_list]
    assert position_list == sorted(position_list)

# URUTAN KOLOM
def test_read_sort_valid_and_desc():
    """Positive: ?sort=title naik, ?sort=-title turun."""
    assert read_sort(MultiDict({"sort": "title"}), ENTRY_COLUMN_LIST) == SortOption("title", False)
    assert read_sort(MultiDict({"sort": "-title"}), ENTRY_COLUMN_LIST) == SortOption("title", True)

@pytest.mark.parametrize("bad_value", ["description", "hack", "--title", "", "title;drop"])
def test_read_sort_rejects_unknown(bad_value):
    """Negative (security): kolom ngasal / yg ga bisa diurutin dicuekin, balik ke urutan bawaan."""
    assert read_sort(MultiDict({"sort": bad_value}), ENTRY_COLUMN_LIST) is None

def test_table_view_toggle_and_default_hidden():
    """Positive: klik judul yg lagi naik -> turun. Deskripsi & Lampiran disembunyiin kalau belum ngatur layout."""
    view = build_table_view(TABLE_ENTRY, MultiDict({"sort": "title"}), {"hidden_list": ["description", "attachment"]})
    column_dict = {column["key"]: column for column in view["column_list"]}
    assert column_dict["title"]["sort_state"] == "asc" and column_dict["title"]["next_sort"] == "-title"
    assert column_dict["owner"]["next_sort"] == "owner"
    assert view["hidden_key_list"] == ["description", "attachment"]

def test_dashboard_sort_by_title(logged_in_client, registered_user, category_dict):
    """Positive: tabel Daftar Link bisa diurutin judul naik & turun."""
    for title in ["Bravo Link", "Alpha Link", "Charlie Link"]:
        create_entry(registered_user, category_dict["Web"], title)
    assert_order(get_card_html(logged_in_client, "/entries/?sort=title", "daftar_link"), ["Alpha Link", "Bravo Link", "Charlie Link"])
    assert_order(get_card_html(logged_in_client, "/entries/?sort=-title", "daftar_link"), ["Charlie Link", "Bravo Link", "Alpha Link"])

def test_sort_kept_in_pagination_and_export(logged_in_client, registered_user, category_dict, read_entry_table):
    """Positive: urutan + filter ikut kebawa ke halaman berikutnya, tombol export, & form Jalankan."""
    for index in range(PER_PAGE + 1):
        create_entry(registered_user, category_dict["Web"], f"Portal {index:02d}")
    url = "/entries/?sort=-title&title=portal*"
    payload = read_entry_table(logged_in_client, url)
    assert payload["pages"] == 2
    assert payload["query"] == {"run": ["1"], "sort": ["-title"], "title": ["portal*"]}
    assert payload["export_url"] == "/export?run=1&sort=-title&title=portal*"
    assert '<input type="hidden" name="sort" value="-title">' in logged_in_client.get(url).get_data(as_text=True)

def test_export_follows_sort(app, registered_user, category_dict):
    """Positive: isi export urutannya sama kayak tabel."""
    for title in ["Bravo Link", "Alpha Link"]:
        create_entry(registered_user, category_dict["Web"], title)
    entry_list, _ = list_visible_entries_for_export(registered_user, sort=SortOption("title", False))
    assert [entry.title for entry in entry_list] == ["Alpha Link", "Bravo Link"]

def test_users_and_audit_sort(admin_client):
    """Positive: tabel Users & Audit Logs juga bisa diurutin, kolom kosong (login terakhir) ga bikin error."""
    log_audit(AUDIT_ACTION_LOGIN_FAILED, "users", actor_email="aaa@luar.com", is_commit=True)
    log_audit(AUDIT_ACTION_LOGIN_FAILED, "users", actor_email="zzz@luar.com", is_commit=True)
    assert_order(get_card_html(admin_client, "/audit-logs/?sort=actor", "daftar_audit"), ["aaa@luar.com", "zzz@luar.com"])
    assert_order(get_card_html(admin_client, "/audit-logs/?sort=-actor", "daftar_audit"), ["zzz@luar.com", "aaa@luar.com"])
    assert admin_client.get("/users/?sort=-last_login").status_code == 200
    assert admin_client.get("/users/?sort=hack").status_code == 200

# LAYOUT KOLOM PER AKUN
def test_save_layout_applied_to_table(logged_in_client, registered_user, category_dict, read_entry_table):
    """Positive: layout disimpen -> kolom Kategori disembunyiin, lebar Judul ngikut, Deskripsi tampil."""
    create_entry(registered_user, category_dict["Web"], "Portal HR")
    response = logged_in_client.post(LAYOUT_URL, json={"table_key": "entry", "hidden_list": ["category"], "width_dict": {"title": 300}})
    assert response.status_code == 200 and response.get_json()["is_success"] is True
    assert registered_user.preference.table_layout["entry"] == {"hidden_list": ["category"], "width_dict": {"title": 300}}
    payload = read_entry_table(logged_in_client, "/entries/?run=1")
    assert payload["layout"] == {"hidden_list": ["category"], "width_dict": {"title": 300}}
    column_dict = {column["key"]: column for column in payload["columns"]}
    assert column_dict["category"]["is_hidden"] is True
    assert column_dict["title"]["width"] == 300
    assert column_dict["description"]["is_hidden"] is False and column_dict["description"]["width"] == 180

def test_layout_saved_per_table(logged_in_client, registered_user):
    """Positive: layout tiap tabel kesimpen sendiri-sendiri."""
    logged_in_client.post(LAYOUT_URL, json={"table_key": "entry", "hidden_list": ["owner"], "width_dict": {}})
    logged_in_client.post(LAYOUT_URL, json={"table_key": "audit", "hidden_list": ["ip"], "width_dict": {}})
    layout_dict = registered_user.preference.table_layout
    assert layout_dict["entry"]["hidden_list"] == ["owner"] and layout_dict["audit"]["hidden_list"] == ["ip"]

@pytest.mark.parametrize("payload, field", [
    ({"table_key": "hack"}, "table_key"),
    ({"table_key": "entry", "hidden_list": ["title"]}, "hidden_list"),
    ({"table_key": "entry", "hidden_list": "category"}, "hidden_list"),
    ({"table_key": "entry", "width_dict": {"title": 5}}, "width_dict"),
    ({"table_key": "entry", "width_dict": {"title": True}}, "width_dict"),
    ({"table_key": "entry", "width_dict": {"hack": 200}}, "width_dict"),
    ({"table_key": "entry", "role": "admin"}, "role"),
])
def test_save_layout_rejects_invalid(logged_in_client, registered_user, payload, field):
    """Negative (security): tabel/kolom ngasal, kolom Judul disembunyiin, lebar aneh, field asing -> 400."""
    response = logged_in_client.post(LAYOUT_URL, json=payload)
    assert response.status_code == 400
    assert field in [error["field"] for error in response.get_json()["error_list"]]
    assert registered_user.preference is None or "entry" not in (registered_user.preference.table_layout or {})

def test_save_layout_requires_json_object(logged_in_client):
    """Negative: body bukan JSON object ditolak."""
    assert logged_in_client.post(LAYOUT_URL, json=["entry"]).status_code == 400
    assert logged_in_client.post(LAYOUT_URL, data="bukan json", content_type="text/plain").status_code == 400

def test_save_layout_requires_login(client):
    """Negative (security): belum login dilempar ke halaman login."""
    response = client.post(LAYOUT_URL, json={"table_key": "entry"})
    assert response.status_code == 302 and "/auth/login" in response.location

def test_save_layout_rejects_missing_csrf_token(monkeypatch):
    """Negative (security): CSRF nyala -> request tanpa token ditolak."""
    monkeypatch.setattr(TestingConfig, "WTF_CSRF_ENABLED", True)
    response = create_app("testing").test_client().post(LAYOUT_URL, json={"table_key": "entry"})
    assert response.status_code == 400

# ALUR PENCARIAN
def test_search_form_and_back_link(logged_in_client, registered_user, category_dict, read_entry_table):
    """Positive: Jalankan langsung ke tabel, link judul bawa alamat tabel, detail punya tombol balik ke tabel itu."""
    entry = create_entry(registered_user, category_dict["Web"], "Portal HR")
    html_text = logged_in_client.get("/entries/?title=portal*").get_data(as_text=True)
    assert 'action="/entries/#daftar_link"' in html_text
    payload = read_entry_table(logged_in_client, "/entries/?title=portal*")
    assert payload["rows"][0]["detail_url"] == f"/entries/{entry.id}?back=/entries/?run%3D1%26title%3Dportal*%23daftar_link"
    detail_html = logged_in_client.get(f"/entries/{entry.id}?back=/entries/?title%3Dportal*%23daftar_link").get_data(as_text=True)
    assert 'href="/entries/?title=portal*#daftar_link" class="btn btn-sm app-toolbar-btn" title="Kembali' in detail_html

@pytest.mark.parametrize("bad_back", ["//evil.com", "https://evil.com", "/\\evil.com", "javascript:alert(1)", "evil.com"])
def test_detail_back_rejects_outside_url(logged_in_client, registered_user, category_dict, bad_back):
    """Negative (security): alamat balik ke luar ALR ditolak, tombolnya balik ke Dashboard."""
    entry = create_entry(registered_user, category_dict["Web"], "Portal HR")
    detail_html = logged_in_client.get(f"/entries/{entry.id}", query_string={"back": bad_back}).get_data(as_text=True)
    assert "evil.com" not in detail_html
    assert 'href="/entries/" class="btn btn-sm app-toolbar-btn" title="Kembali' in detail_html

def test_safe_back_url():
    """Positive & negative: cuma path di dalem ALR yg diterima."""
    assert get_safe_back_url("/categories/3?title=a*#daftar_link") == "/categories/3?title=a*#daftar_link"
    assert get_safe_back_url("/ spasi") is None
    assert get_safe_back_url(None) is None

def test_settings_text_matches_save_button(logged_in_client):
    """Positive: petunjuk di Settings sesuai perilaku customizer (harus klik Simpan)."""
    html_text = logged_in_client.get("/settings/").get_data(as_text=True)
    assert "tersimpan otomatis" not in html_text
    assert "klik <strong>Simpan</strong>" in html_text
