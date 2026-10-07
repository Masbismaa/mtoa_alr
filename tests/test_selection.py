"""Test Select Screen: wildcard *ad / ad*, Multi Selection (sertakan/kecualikan), pilihan multi, rentang tanggal, menu terkunci."""
from werkzeug.datastructures import MultiDict
from app.services.access_entry_service import create_access_entry
from app.services.audit_service import log_audit
from app.services.group_service import create_group
from app.utils.constants import AUDIT_ACTION_LOGIN_FAILED, SELECTION_MAX_VALUE_COUNT, VISIBILITY_PRIVATE, VISIBILITY_PUBLIC
from app.utils.query_helper import build_like_pattern
from app.utils.selection import describe_selection, read_text_selection, text_field

def create_entry(user, category, title, url="", address="", visibility=VISIBILITY_PRIVATE):
    """Helper: bikin link contoh."""
    return create_access_entry(user, {
        "category_id": category.id, "title": title, "url": url,
        "address": address, "port": "22" if address else "", "username": "", "access_note": "", "description": "",
        "visibility": visibility,
    })

def get_html(client, url):
    """Helper: isi halaman."""
    return client.get(url).get_data(as_text=True)

def get_table_html(client, url):
    """Helper: isi kartu tabel Daftar Link aja (bagian lain halaman ga ikut dicek)."""
    return get_html(client, url).split('id="daftar_link"')[1].split("data-status-bar")[0]

def test_like_pattern_wildcard():
    """Positive: tanpa * = mengandung, ad* = diawali, *ad = diakhiri, a*d = a...d."""
    assert build_like_pattern("ad") == "%ad%"
    assert build_like_pattern("ad*") == "ad%"
    assert build_like_pattern("*ad") == "%ad"
    assert build_like_pattern("*ad*") == "%ad%"
    assert build_like_pattern("a*d") == "a%d"

def test_like_pattern_escapes_sql_wildcard():
    """Negative (security): % dan _ yg diketik user tetep huruf biasa, bukan wildcard SQL."""
    assert build_like_pattern("100%") == "%100\\%%"
    assert build_like_pattern("a_b*") == "a\\_b%"

def test_read_text_selection_cleans_and_limits():
    """Negative: nilai kosong & dobel dibuang, kepanjangan dipotong, jumlah dibatesin."""
    args = MultiDict([("title", " portal* "), ("title", "portal*"), ("title", ""), ("title__not", "x" * 500)]
                     + [("access", f"nilai{index}") for index in range(SELECTION_MAX_VALUE_COUNT + 5)])
    selection = read_text_selection(args, "title")
    assert selection.include_list == ["portal*"]
    assert len(selection.exclude_list[0]) == 100
    assert len(read_text_selection(args, "access").include_list) == SELECTION_MAX_VALUE_COUNT

def test_describe_selection_text():
    """Positive: kriteria ditulis jadi teks buat sheet Info export."""
    args = MultiDict([("q", "vpn"), ("title", "portal*"), ("title__not", "*test*")])
    assert describe_selection(args, [text_field("title", "Judul")]) == ['Kata kunci "vpn"', 'Judul "portal*" kecuali "*test*"']

def test_dashboard_wildcard_prefix_suffix(logged_in_client, registered_user, category_dict):
    """Positive: portal* = diawali portal, *hr = diakhiri hr."""
    web = category_dict["Web"]
    create_entry(registered_user, web, "Portal HR", "https://hr.spindo.com")
    create_entry(registered_user, web, "Portal VPN", "https://vpn.spindo.com")
    create_entry(registered_user, web, "Router Portal", "https://router.spindo.com")
    html_text = get_table_html(logged_in_client, "/entries/?title=portal*")
    assert "Portal HR" in html_text and "Portal VPN" in html_text and "Router Portal" not in html_text
    html_text = get_table_html(logged_in_client, "/entries/?title=*hr")
    assert "Portal HR" in html_text and "Portal VPN" not in html_text

def test_dashboard_multi_include_exclude(logged_in_client, registered_user, category_dict):
    """Positive: Multi Selection: sertakan banyak nilai (atau), kecualikan buang yg cocok."""
    web = category_dict["Web"]
    create_entry(registered_user, web, "Portal HR", "https://hr.spindo.com")
    create_entry(registered_user, web, "Portal VPN", "https://vpn.spindo.com")
    create_entry(registered_user, web, "Router Lantai", "https://router.spindo.com")
    html_text = get_table_html(logged_in_client, "/entries/?title=portal*&title__not=*vpn")
    assert "Portal HR" in html_text and "Portal VPN" not in html_text and "Router Lantai" not in html_text
    html_text = get_table_html(logged_in_client, "/entries/?title=*hr&title=router*")
    assert "Portal HR" in html_text and "Router Lantai" in html_text and "Portal VPN" not in html_text

def test_dashboard_percent_is_literal(logged_in_client, registered_user, category_dict):
    """Negative (security): ngetik % ga bikin semua data ikut."""
    create_entry(registered_user, category_dict["Web"], "Diskon 100%", "https://a.spindo.com")
    create_entry(registered_user, category_dict["Web"], "Portal Lain", "https://b.spindo.com")
    html_text = get_table_html(logged_in_client, "/entries/?title=100%25")
    assert "Diskon 100%" in html_text and "Portal Lain" not in html_text

def test_dashboard_access_owner_and_choice(logged_in_client, registered_user, other_user, category_dict):
    """Positive: URL/Address (url atau address), Dibuat Oleh, kategori & visibilitas lebih dari satu."""
    create_entry(registered_user, category_dict["Web"], "Portal HR", "https://hr.spindo.com")
    create_entry(registered_user, category_dict["Network"], "Switch Core", address="10.0.0.2")
    create_entry(other_user, category_dict["Web"], "Public Orang", "https://lain.spindo.com", visibility=VISIBILITY_PUBLIC)
    html_text = get_table_html(logged_in_client, "/entries/?access=10.0.*")
    assert "Switch Core" in html_text and "Portal HR" not in html_text
    html_text = get_table_html(logged_in_client, "/entries/?owner=user.lain*")
    assert "Public Orang" in html_text and "Portal HR" not in html_text
    network_id, web_id = category_dict["Network"].id, category_dict["Web"].id
    html_text = get_table_html(logged_in_client, f"/entries/?category_id={network_id}&category_id={web_id}&visibility=private")
    assert "Switch Core" in html_text and "Portal HR" in html_text and "Public Orang" not in html_text

def test_dashboard_date_range(logged_in_client, registered_user, category_dict):
    """Negative: rentang tanggal sebelum data dibuat -> kosong."""
    create_entry(registered_user, category_dict["Web"], "Portal HR", "https://hr.spindo.com")
    assert "Portal HR" not in get_table_html(logged_in_client, "/entries/?created_to=2000-01-01")
    assert "Portal HR" in get_table_html(logged_in_client, "/entries/?created_from=2000-01-01")

def test_dashboard_bad_values_ignored(logged_in_client):
    """Negative: nilai ngaco (status/visibilitas/tanggal/kategori asal) dicuekin, halaman tetep kebuka."""
    response = logged_in_client.get("/entries/?status=hack&visibility=hack&category_id=xyz&created_from=kemarin&title__not=")
    assert response.status_code == 200

def test_export_follows_selection(logged_in_client, registered_user, category_dict):
    """Positive: export ikut kriteria Select Screen + kriterianya kecatat."""
    create_entry(registered_user, category_dict["Web"], "Portal HR", "https://hr.spindo.com")
    create_entry(registered_user, category_dict["Web"], "Router Lantai", "https://router.spindo.com")
    response = logged_in_client.get("/export?title=portal*")
    assert response.status_code == 200
    assert response.data[:2] == b"PK"

def test_category_browse_selection(logged_in_client, registered_user, category_dict):
    """Positive: halaman kategori juga punya Select Screen."""
    web = category_dict["Web"]
    create_entry(registered_user, web, "Portal HR", "https://hr.spindo.com")
    create_entry(registered_user, web, "Router Lantai", "https://router.spindo.com")
    html_text = get_html(logged_in_client, f"/categories/{web.id}?title=*hr")
    assert "Kriteria Pencarian" in html_text
    assert "Portal HR" in html_text and "Router Lantai" not in html_text

def test_users_selection(admin_client, admin_user, registered_user):
    """Positive: Users bisa dicari pake wildcard & dikecualikan."""
    html_text = get_html(admin_client, "/users/?name=user.login*")
    assert registered_user.email in html_text
    assert admin_user.email not in html_text.split('id="filter_keyword"')[1]
    html_text = get_html(admin_client, "/users/?name=*@spindo.com&name__not=admin*&status=active&status=locked")
    assert registered_user.email in html_text
    assert admin_user.email not in html_text.split('id="filter_keyword"')[1]

def test_audit_selection(admin_client):
    """Positive: Audit Logs bisa difilter pelaku pake wildcard + aksi lebih dari satu."""
    log_audit(AUDIT_ACTION_LOGIN_FAILED, "users", actor_email="penyusup@luar.com", is_commit=True)
    assert "penyusup@luar.com" in get_html(admin_client, "/audit-logs/?actor=*@luar.com&action=login_failed&action=login")
    assert "penyusup@luar.com" not in get_html(admin_client, "/audit-logs/?actor=*@luar.com&action=logout")

def test_groups_selection(logged_in_client, registered_user, other_user):
    """Positive: Groups bisa dicari nama (wildcard) & peran saya."""
    create_group(registered_user, {"name": "Tim Network"})
    create_group(registered_user, {"name": "Proyek ERP"})
    html_text = get_html(logged_in_client, "/groups/?name=tim*")
    assert "Tim Network" in html_text and "Proyek ERP" not in html_text
    assert "Tim Network" not in get_html(logged_in_client, "/groups/?role=member")

def test_locked_menu_visible_but_not_clickable(logged_in_client):
    """Positive + security: user biasa liat menu admin dgn gembok, tapi ga ada link-nya & halamannya tetep 403."""
    html_text = get_html(logged_in_client, "/")
    assert "Audit Logs" in html_text and "Users" in html_text
    assert 'href="/audit-logs/"' not in html_text and 'href="/users/"' not in html_text
    assert "nav-link-locked" in html_text
    assert 'data-locked-message="Kamu belum punya otoritas buat buka menu Users. Khusus admin."' in html_text
    assert logged_in_client.get("/users/").status_code == 403
