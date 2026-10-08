"""Test layar ala SAP: judul layar Display/Create/Change (Data Link = Access Link), kepala halaman di-remark,
Daftar Link baru nampilin tabel abis Jalankan, filter per kolom di tabel."""
import re
import pytest
from app.services.access_entry_service import create_access_entry
from app.services.audit_service import log_audit
from app.services.group_service import create_group
from app.utils.constants import AUDIT_ACTION_LOGIN_FAILED, VISIBILITY_PRIVATE, VISIBILITY_PUBLIC

def create_entry(user, category, title, visibility=VISIBILITY_PRIVATE):
    """Helper: bikin link contoh, URL-nya beda tiap judul (URL dobel ditolak)."""
    return create_access_entry(user, {
        "category_id": category.id, "title": title, "url": f"https://{title.lower().replace(' ', '-')}.spindo.com",
        "address": "", "port": "", "username": "", "access_note": "", "description": "", "visibility": visibility,
    })

def get_html(client, url):
    """Helper: isi halaman."""
    return client.get(url).get_data(as_text=True)

def get_screen_title(html_text):
    """Helper: judul layar di tengah title bar atas."""
    return re.search(r'<div class="app-topbar-title" title="([^"]*)">', html_text).group(1)

# JUDUL LAYAR & KEPALA HALAMAN
def test_access_link_screen_titles(logged_in_client, registered_user, category_dict):
    """Positive: layar Data Link judulnya Access Link + Display/Create/Change sesuai aksinya."""
    entry = create_entry(registered_user, category_dict["Web"], "Portal HR")
    assert get_screen_title(get_html(logged_in_client, "/entries/")) == "Display Access Link"
    assert get_screen_title(get_html(logged_in_client, f"/entries/{entry.id}")) == "Display Access Link: Portal HR"
    assert get_screen_title(get_html(logged_in_client, "/entries/new")) == "Create Access Link"
    assert get_screen_title(get_html(logged_in_client, f"/entries/{entry.id}/edit")) == "Change Access Link: Portal HR"

def test_other_screen_titles(logged_in_client, registered_user):
    """Positive: layar lain ikut pola Display/Create/Change, Dashboard & Settings tetep namanya."""
    group = create_group(registered_user, {"name": "Tim Network"})
    assert get_screen_title(get_html(logged_in_client, "/groups/")) == "Display Group"
    assert get_screen_title(get_html(logged_in_client, f"/groups/{group.id}")) == "Display Group: Tim Network"
    assert get_screen_title(get_html(logged_in_client, "/groups/new")) == "Create Group"
    assert get_screen_title(get_html(logged_in_client, f"/groups/{group.id}/edit")) == "Change Group: Tim Network"
    assert get_screen_title(get_html(logged_in_client, "/")) == "Dashboard"
    assert get_screen_title(get_html(logged_in_client, "/settings/")) == "Settings"

def test_page_header_remarked(logged_in_client):
    """Positive: kepala halaman lama (judul kecil + judul + keterangan) udah ga tampil, judul cukup di title bar & toolbar."""
    html_text = get_html(logged_in_client, "/entries/")
    assert 'class="page-header' not in html_text and 'class="page-pretitle"' not in html_text
    assert '<div class="app-toolbar-title d-lg-none">Display Access Link</div>' in html_text

# DAFTAR LINK: TABEL ABIS JALANKAN
def test_entry_list_hides_table_before_run(logged_in_client, registered_user, category_dict):
    """Positive: buka Daftar Link -> cuma Kriteria Pencarian + petunjuk, tabel belum ada."""
    create_entry(registered_user, category_dict["Web"], "Portal HR")
    html_text = get_html(logged_in_client, "/entries/")
    assert "data-selection-form" in html_text and "data-selection-hint" in html_text
    assert 'id="daftar_link"' not in html_text and "Portal HR" not in html_text
    assert '<input type="hidden" name="run" value="1">' in html_text

def test_entry_list_shows_table_after_run(logged_in_client, registered_user, category_dict, read_entry_table):
    """Positive: Jalankan tanpa kriteria -> semua link, penanda run ikut kebawa ke urutan/halaman."""
    create_entry(registered_user, category_dict["Web"], "Portal HR")
    html_text = get_html(logged_in_client, "/entries/?run=1")
    assert 'id="daftar_link"' in html_text and "data-selection-hint" not in html_text
    payload = read_entry_table(logged_in_client, "/entries/?run=1")
    assert [row["title"] for row in payload["rows"]] == ["Portal HR"]
    assert payload["heading"]["text"] == "Seluruh link: 1 data"
    assert payload["query"] == {"run": ["1"]}
    assert {column["key"]: column["next_sort"] for column in payload["columns"]}["title"] == "title"

def test_sidebar_filter_shows_table(logged_in_client, registered_user, category_dict):
    """Positive: menu Link Public (bawa kriteria) langsung nampilin tabel."""
    create_entry(registered_user, category_dict["Web"], "Portal Umum", visibility=VISIBILITY_PUBLIC)
    html_text = get_html(logged_in_client, "/entries/?visibility=public")
    assert 'id="daftar_link"' in html_text and "Portal Umum" in html_text

# FILTER PER KOLOM
def test_column_filter_row(logged_in_client, registered_user, category_dict, read_entry_table):
    """Positive: filter per kolom ada (teks & pilihan), nilai yg kepake keisi, urutan & penanda run ikut kebawa."""
    create_entry(registered_user, category_dict["Web"], "Portal HR")
    payload = read_entry_table(logged_in_client, "/entries/?run=1&title=portal*&sort=-title")
    filter_dict = {column["key"]: column["filter"] for column in payload["columns"]}
    assert filter_dict["title"] == {"key": "title", "kind": "text", "value": "portal*", "option_list": [], "is_locked": False}
    assert filter_dict["visibility"]["kind"] == "choice"
    assert filter_dict["description"] is None
    assert payload["sort"] == "-title"
    assert payload["query"] == {"run": ["1"], "sort": ["-title"], "title": ["portal*"]}

def test_column_filter_locked_for_multi_value(logged_in_client, registered_user, category_dict, read_entry_table):
    """Negative: isian yg lagi diisi banyak nilai (Multi Selection) dikunci di baris filter, nilainya tetep kebawa."""
    create_entry(registered_user, category_dict["Web"], "Portal HR")
    payload = read_entry_table(logged_in_client, "/entries/?title=portal*&title=router*")
    assert {column["key"]: column["filter"] for column in payload["columns"]}["title"]["is_locked"] is True
    assert payload["query"]["title"] == ["portal*", "router*"]

def test_column_filter_filters_table(logged_in_client, registered_user, category_dict):
    """Positive: isi filter kolom Judul (sama kayak isian Kriteria) -> tabel cuma nampilin yg cocok."""
    create_entry(registered_user, category_dict["Web"], "Portal HR")
    create_entry(registered_user, category_dict["Web"], "Router Lantai")
    table_html = get_html(logged_in_client, "/entries/?run=1&title=router*").split('id="daftar_link"')[1].split("data-status-bar")[0]
    assert "Router Lantai" in table_html and "Portal HR" not in table_html

@pytest.mark.parametrize("url, form_id", [("/users/", "column_filter_user"), ("/audit-logs/", "column_filter_audit")])
def test_column_filter_on_admin_tables(admin_client, url, form_id):
    """Positive: tabel Users & Audit Logs juga punya filter per kolom."""
    log_audit(AUDIT_ACTION_LOGIN_FAILED, "users", actor_email="penyusup@luar.com", is_commit=True)
    html_text = get_html(admin_client, url)
    assert f'id="{form_id}"' in html_text and f'form="{form_id}"' in html_text

def test_column_filter_keeps_run_marker(logged_in_client, registered_user, category_dict, read_entry_table):
    """Positive: dibuka dari menu (tanpa run) lalu filter kolom dikosongin -> tabel tetep tampil (run ikut kebawa)."""
    create_entry(registered_user, category_dict["Web"], "Portal Umum", visibility=VISIBILITY_PUBLIC)
    payload = read_entry_table(logged_in_client, "/entries/?visibility=public")
    assert payload["query"] == {"run": ["1"], "visibility": ["public"]}

def test_page_info_still_shown(logged_in_client, registered_user, category_dict):
    """Positive: keterangan halaman (kategori & visibilitas di detail) tetep tampil walau kepala halaman di-remark."""
    entry = create_entry(registered_user, category_dict["Web"], "Portal HR")
    page_info_html = get_html(logged_in_client, f"/entries/{entry.id}").split('class="page-info"')[1].split("data-flash-list")[0]
    assert "Web" in page_info_html and "Private" in page_info_html
