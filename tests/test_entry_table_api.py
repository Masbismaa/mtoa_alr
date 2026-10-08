"""Test tabel link React: API table-data (Daftar Link & isi kategori), data awal yg ditempel di halaman,
kontrak bentuk data (harus sama kayak frontend/src/test/makePayload.js), keamanan, & tag script hasil build Vite."""
import pytest
from app.models import Category
from app.services.access_entry_service import create_access_entry
from app.services.category_service import toggle_category_active
from app.utils import vite_manifest
from app.utils.constants import PER_PAGE, VISIBILITY_PRIVATE, VISIBILITY_PUBLIC

API_URL = "/entries/table-data"

# kunci data tabel & data baris yg dipake React. Nambah/ganti kunci = update frontend juga
PAYLOAD_KEY_SET = {
    "table_key", "api_url", "page_url", "layout_url", "anchor", "columns", "layout", "default_layout", "default_width_dict",
    "sort", "query", "page", "pages", "total", "page_list", "rows", "is_filtered", "heading", "empty", "export_url",
}
ROW_KEY_SET = {
    "id", "title", "detail_url", "category_label", "category_url", "access_text", "description", "visibility",
    "visibility_label", "status", "status_label", "status_title", "attachment_count", "owner_name", "created_text",
}
COLUMN_KEY_SET = {"key", "label", "width", "is_hidden", "is_sortable", "is_hideable", "sort_state", "next_sort", "filter"}

def create_entry(user, category, title, visibility=VISIBILITY_PRIVATE, **override_dict):
    """Helper: link contoh, URL-nya beda tiap judul (URL dobel ditolak)."""
    entry_dict = {
        "category_id": category.id, "title": title, "url": f"https://{title.lower().replace(' ', '-')}.spindo.com",
        "address": "", "port": "", "username": "", "access_note": "", "description": "", "visibility": visibility,
    }
    entry_dict.update(override_dict)
    return create_access_entry(user, entry_dict)

def get_api_data(client, url):
    """Helper: panggil API, pastiin sukses, balikin isi data-nya."""
    response = client.get(url)
    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_json()
    assert body["is_success"] is True
    return body["data"]

def make_sub_category(parent, name):
    """Helper: sub-kategori aktif."""
    from app.extensions import db

    category = Category(parent_id=parent.id, name=name, is_active=True)
    db.session.add(category)
    db.session.commit()
    return category

# KONTRAK DATA
def test_payload_and_row_shape(logged_in_client, registered_user, category_dict):
    """Positive: bentuk data persis yg dipake React (frontend/src/test/makePayload.js)."""
    create_entry(registered_user, category_dict["Web"], "Portal HR")
    data = get_api_data(logged_in_client, API_URL + "?run=1")
    assert set(data) == PAYLOAD_KEY_SET
    assert set(data["rows"][0]) == ROW_KEY_SET
    assert all(set(column) == COLUMN_KEY_SET for column in data["columns"])

def test_page_and_api_return_same_data(logged_in_client, registered_user, category_dict, read_entry_table):
    """Positive: data awal di halaman = balasan API dgn parameter yg sama (satu fungsi yg sama di server)."""
    for title in ["Portal HR", "Router Lantai"]:
        create_entry(registered_user, category_dict["Web"], title)
    query_text = "run=1&title=*a*&sort=-title"
    assert read_entry_table(logged_in_client, f"/entries/?{query_text}") == get_api_data(logged_in_client, f"{API_URL}?{query_text}")

def test_row_values(logged_in_client, registered_user, category_dict):
    """Positive: isi baris udah siap tampil (label, address:port, URL detail bawa alamat balik)."""
    entry = create_entry(registered_user, category_dict["Network"], "Switch Core", url="", address="10.0.0.1", port="22")
    row = get_api_data(logged_in_client, API_URL + "?run=1")["rows"][0]
    assert row["access_text"] == "10.0.0.1:22"
    assert row["visibility_label"] == "Private" and row["status_label"] == "Belum dicek"
    assert row["detail_url"] == f"/entries/{entry.id}?back=/entries/?run%3D1%23daftar_link"
    assert row["created_text"].endswith("WIB")

# HAK AKSES & KEAMANAN
def test_api_requires_login_with_json_401(client):
    """Negative (security): belum login -> 401 JSON (bukan redirect HTML yg diem-diem diikutin fetch)."""
    response = client.get(API_URL + "?run=1")
    assert response.status_code == 401
    assert response.get_json()["is_success"] is False
    assert "Sesi login habis" in response.get_json()["message"]

def test_api_respects_visibility(logged_in_client, registered_user, other_user, category_dict):
    """Negative (security): link Private orang lain ga pernah ikut, Public ikut."""
    create_entry(other_user, category_dict["Web"], "Rahasia Orang", visibility=VISIBILITY_PRIVATE)
    create_entry(other_user, category_dict["Web"], "Umum Orang", visibility=VISIBILITY_PUBLIC)
    create_entry(registered_user, category_dict["Web"], "Punya Sendiri")
    titles = {row["title"] for row in get_api_data(logged_in_client, API_URL + "?run=1")["rows"]}
    assert titles == {"Umum Orang", "Punya Sendiri"}

@pytest.mark.parametrize("query_text", [
    "sort=hack", "sort=title;drop table users", "page=abc", "page=-1", "visibility=hack", "category_id=xyz", "created_from=kemarin",
])
def test_api_ignores_bad_params(logged_in_client, registered_user, category_dict, query_text):
    """Negative: parameter ngasal dicuekin (bukan error 500), urutan balik ke bawaan."""
    create_entry(registered_user, category_dict["Web"], "Portal HR")
    data = get_api_data(logged_in_client, f"{API_URL}?run=1&{query_text}")
    assert data["page"] == 1 and data["sort"] == ""
    assert len(data["rows"]) <= 1

def test_title_is_escaped_in_page(logged_in_client, registered_user, category_dict, read_entry_table):
    """Negative (security): karakter yg lolos sanitasi (kutip, < >, &) ga bisa keluar dari atribut data-entry-table.
    Tag HTML-nya sendiri udah dibuang sanitize_text pas disimpen; React nampilin sisanya sebagai teks (dites di frontend)."""
    tricky_title = "1 < 2 > 0 'kutip' \"dua\" & dan"
    create_entry(registered_user, category_dict["Web"], tricky_title, url="https://hack.spindo.com")
    html_text = logged_in_client.get("/entries/?run=1").get_data(as_text=True)
    attribute_html = html_text.split("data-entry-table='")[1].split("'>")[0]
    assert "'" not in attribute_html and "<" not in attribute_html and ">" not in attribute_html
    assert read_entry_table(logged_in_client, "/entries/?run=1")["rows"][0]["title"] == tricky_title

def test_csp_blocks_inline_script(logged_in_client, category_dict):
    """Positive (security): CSP cuma ngizinin script dari server sendiri, halaman tabel tetep jalan (tanpa script inline)."""
    response = logged_in_client.get("/entries/?run=1")
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    html_text = response.get_data(as_text=True)
    assert '<script type="module" src="/static/dist/assets/entry_table-' in html_text
    assert "<script>" not in html_text

# HALAMAN & URUTAN
def test_page_out_of_range_goes_to_last_page(logged_in_client, registered_user, category_dict):
    """Positive: nomor halaman kebablasan (misal abis data dihapus) -> halaman terakhir, bukan tabel kosong palsu."""
    for index in range(PER_PAGE + 2):
        create_entry(registered_user, category_dict["Web"], f"Portal {index:02d}")
    data = get_api_data(logged_in_client, API_URL + "?run=1&page=99")
    assert data["page"] == 2 and len(data["rows"]) == 2 and data["empty"] is None

def test_sort_and_next_sort(logged_in_client, registered_user, category_dict):
    """Positive: urutan dipake, judul kolom yg lagi naik -> klik berikutnya turun."""
    for title in ["Bravo", "Alpha", "Charlie"]:
        create_entry(registered_user, category_dict["Web"], title)
    data = get_api_data(logged_in_client, API_URL + "?run=1&sort=title")
    assert [row["title"] for row in data["rows"]] == ["Alpha", "Bravo", "Charlie"]
    title_column = next(column for column in data["columns"] if column["key"] == "title")
    assert title_column["sort_state"] == "asc" and title_column["next_sort"] == "-title"

def test_empty_states(logged_in_client, category_dict):
    """Positive: kosong karena filter vs emang belum ada data, teks & tombolnya beda."""
    filtered = get_api_data(logged_in_client, API_URL + "?run=1&q=zzzz")
    assert filtered["is_filtered"] is True and filtered["empty"]["title"] == 'Tidak ada hasil untuk "zzzz".'
    assert filtered["empty"]["action"]["label"] == "Reset filter" and filtered["export_url"] is None
    unfiltered = get_api_data(logged_in_client, API_URL + "?run=1")
    assert unfiltered["is_filtered"] is False and unfiltered["empty"]["action"]["url"] == "/entries/new"

def test_index_without_run_has_no_table(logged_in_client, registered_user, category_dict):
    """Positive: Daftar Link belum Jalankan -> cuma Kriteria Pencarian, tabel & script-nya ga dimuat."""
    create_entry(registered_user, category_dict["Web"], "Portal HR")
    html_text = logged_in_client.get("/entries/").get_data(as_text=True)
    assert "data-entry-table" not in html_text and "data-selection-hint" in html_text

# HALAMAN KATEGORI
def test_category_api_only_direct_entries(logged_in_client, registered_user, category_dict):
    """Positive: isi kategori = link yg langsung di kategori itu (sub-nya ga ikut), tanpa kolom Kategori & tombol export."""
    web = category_dict["Web"]
    sub = make_sub_category(web, "SAP")
    create_entry(registered_user, web, "Langsung Web")
    create_entry(registered_user, sub, "Di SAP")
    data = get_api_data(logged_in_client, f"/categories/{web.id}/table-data")
    assert [row["title"] for row in data["rows"]] == ["Langsung Web"]
    assert "category" not in {column["key"] for column in data["columns"]}
    assert data["export_url"] is None and data["heading"] == {"icon": "link", "text": "Link di Web", "count_text": "1 data"}
    assert data["api_url"] == f"/categories/{web.id}/table-data" and data["page_url"] == f"/categories/{web.id}"
    assert "run" not in data["query"]

def test_category_api_empty_text_mentions_sub_category(logged_in_client, category_dict):
    """Positive: kategori kosong yg punya sub -> kasih tau link lainnya ada di sub-kategori."""
    web = category_dict["Web"]
    make_sub_category(web, "SAP")
    data = get_api_data(logged_in_client, f"/categories/{web.id}/table-data")
    assert data["empty"]["subtitle"] == "Link lainnya ada di sub-kategori di atas."

def test_category_api_not_found_and_inactive(logged_in_client, admin_user, category_dict):
    """Negative: kategori ga ada / nonaktif (buat user biasa) -> 404 JSON."""
    assert logged_in_client.get("/categories/999999/table-data").status_code == 404
    sub = make_sub_category(category_dict["Web"], "Lama")
    toggle_category_active(admin_user, sub)
    response = logged_in_client.get(f"/categories/{sub.id}/table-data")
    assert response.status_code == 404 and response.get_json()["is_success"] is False

def test_category_api_requires_login(client, category_dict):
    """Negative (security): belum login -> 401 JSON."""
    assert client.get(f"/categories/{category_dict['Web'].id}/table-data").status_code == 401

# BUILD VITE
def test_missing_manifest_gives_clear_error(app, monkeypatch, tmp_path):
    """Negative: lupa build frontend -> error yg nyebut cara benerinnya (bukan halaman rusak diem-diem)."""
    monkeypatch.setattr(app, "static_folder", str(tmp_path))
    monkeypatch.setattr(vite_manifest, "_manifest_cache", {"mtime": None, "data": None})
    with app.test_request_context("/"):
        with pytest.raises(RuntimeError, match="npm run build"):
            vite_manifest.vite_tags("entry_table")

def test_unknown_vite_entry(app):
    """Negative: nama entry salah ketik -> error yg nyebut vite.config.js."""
    with app.test_request_context("/"):
        with pytest.raises(RuntimeError, match="vite.config.js"):
            vite_manifest.vite_tags("salah_ketik")
