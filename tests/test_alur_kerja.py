"""Test alur kerja ala SAP GUI: toolbar aplikasi (Kembali/Keluar/Batal/Simpan/Bantuan), status bar,
peringatan form belum disimpan, dan konteks daftar asal yg kebawa lewat detail -> edit -> simpan/batal/hapus."""
import pytest
from app.extensions import db
from app.models import AccessEntry
from app.services.access_entry_service import create_access_entry
from app.utils.constants import VISIBILITY_PRIVATE

BACK_URL = "/entries/?title=portal*#daftar_link"
BACK_PARAM = "/entries/?title%3Dportal*%23daftar_link"

def create_entry(user, category, title="Portal HR"):
    """Helper: bikin link contoh (private). URL-nya beda tiap judul, soalnya URL dobel ditolak."""
    return create_access_entry(user, {
        "category_id": category.id, "title": title, "url": f"https://{title.lower().replace(' ', '-')}.spindo.com",
        "address": "", "port": "", "username": "", "access_note": "", "description": "", "visibility": VISIBILITY_PRIVATE,
    })

def get_html(client, url):
    """Helper: isi halaman."""
    return client.get(url).get_data(as_text=True)

# KONTEKS DAFTAR ASAL LEWAT EDIT
def test_detail_passes_back_to_edit_and_delete(logged_in_client, registered_user, category_dict):
    """Positive: dari detail, tombol Edit & Hapus bawa alamat tabel asal. Toolbar Kembali ke tabel itu."""
    entry = create_entry(registered_user, category_dict["Web"])
    html_text = get_html(logged_in_client, f"/entries/{entry.id}?back={BACK_PARAM}")
    assert f'href="/entries/{entry.id}/edit?back={BACK_PARAM}"' in html_text
    assert f'action="/entries/{entry.id}/delete?back={BACK_PARAM}"' in html_text
    assert f'href="{BACK_URL}" class="btn btn-sm app-toolbar-btn" title="Kembali ke layar sebelumnya"' in html_text

def test_edit_keeps_back_on_cancel_and_save(logged_in_client, registered_user, category_dict):
    """Positive: di Edit, Batal & Simpan balik ke detail yg masih inget tabel asalnya."""
    entry = create_entry(registered_user, category_dict["Web"])
    detail_url = f"/entries/{entry.id}?back={BACK_PARAM}"
    html_text = get_html(logged_in_client, f"/entries/{entry.id}/edit?back={BACK_PARAM}")
    assert f'href="{detail_url}" class="btn btn-sm app-toolbar-btn" title="Batalkan' in html_text
    assert f'action="/entries/{entry.id}/edit?back={BACK_PARAM}"' in html_text
    response = logged_in_client.post(f"/entries/{entry.id}/edit?back={BACK_PARAM}", data={
        "category_id": str(category_dict["Web"].id), "title": "Portal HR Baru", "url": "https://hr.spindo.com",
        "visibility": VISIBILITY_PRIVATE,
    })
    assert response.status_code == 302 and response.location.endswith(detail_url)

def test_delete_returns_to_list(logged_in_client, registered_user, category_dict):
    """Positive: abis hapus balik ke tabel asal (filter tetep), tanpa alamat asal ke Daftar Link."""
    first_entry = create_entry(registered_user, category_dict["Web"], "Portal Satu")
    second_entry = create_entry(registered_user, category_dict["Web"], "Portal Dua")
    response = logged_in_client.post(f"/entries/{first_entry.id}/delete?back={BACK_PARAM}")
    assert response.status_code == 302 and response.location.endswith(BACK_URL)
    response = logged_in_client.post(f"/entries/{second_entry.id}/delete")
    assert response.location.endswith("/entries/")
    assert db.session.execute(db.select(db.func.count(AccessEntry.id))).scalar() == 0

@pytest.mark.parametrize("bad_back", ["//evil.com", "https://evil.com"])
def test_edit_ignores_outside_back(logged_in_client, registered_user, category_dict, bad_back):
    """Negative (security): alamat balik ke luar ALR dicuekin di Edit & Hapus."""
    entry = create_entry(registered_user, category_dict["Web"])
    html_text = logged_in_client.get(f"/entries/{entry.id}/edit", query_string={"back": bad_back}).get_data(as_text=True)
    assert "evil.com" not in html_text
    response = logged_in_client.post(f"/entries/{entry.id}/delete", query_string={"back": bad_back})
    assert response.location.endswith("/entries/")

def test_create_from_list_cancel_back_to_list(logged_in_client):
    """Positive: Tambah Link dari Daftar Link -> Batal balik ke tabel yg sama."""
    html_text = get_html(logged_in_client, f"/entries/new?back={BACK_PARAM}")
    assert f'href="{BACK_URL}" class="btn btn-sm app-toolbar-btn" title="Batalkan' in html_text

# TOOLBAR, FORM GUARD, STATUS BAR
def test_form_page_toolbar_save_and_guard(logged_in_client, category_dict):
    """Positive: form punya tombol Simpan di toolbar (selalu kelihatan), penjaga perubahan, mode Ubah."""
    html_text = get_html(logged_in_client, "/entries/new")
    assert '<button type="submit" form="entry_form"' in html_text
    assert 'id="entry_form"' in html_text and "data-form-guard" in html_text
    assert "Mode: <strong>Ubah</strong>" in html_text

def test_view_page_toolbar_disables_save(logged_in_client):
    """Positive: layar lihat-lihat: Simpan & Batal dinonaktifin, posisinya tetep ada, mode Lihat."""
    html_text = get_html(logged_in_client, "/entries/")
    assert 'title="Simpan ga tersedia di layar ini"' in html_text
    assert 'title="Batal ga tersedia di layar ini"' in html_text
    assert "Mode: <strong>Lihat</strong>" in html_text

def test_dashboard_toolbar_back_and_exit_disabled(logged_in_client):
    """Positive: di Dashboard (layar paling atas) Kembali & Keluar dinonaktifin."""
    html_text = get_html(logged_in_client, "/")
    assert 'title="Kembali ga tersedia di layar ini"' in html_text
    assert 'title="Keluar ga tersedia di layar ini"' in html_text

@pytest.mark.parametrize("url", ["/groups/new", "/settings/"])
def test_toolbar_and_status_bar_on_every_page(logged_in_client, url):
    """Positive: toolbar & status bar ada di semua layar, environment kelihatan."""
    html_text = get_html(logged_in_client, url)
    assert 'role="toolbar" aria-label="Toolbar layar"' in html_text
    assert 'title="Environment server">TEST</span>' in html_text
    assert 'id="help_dialog"' in html_text

def test_help_dialog_has_page_help(logged_in_client):
    """Positive: Bantuan di Daftar Link ngejelasin cara pakai layar itu."""
    html_text = get_html(logged_in_client, "/entries/")
    help_html = html_text.split('id="help_dialog"')[1]
    assert "Multi Selection" in help_html and "Kriteria Pencarian" in help_html

def test_multi_selection_dialog_has_counter(logged_in_client):
    """Positive: dialog Multi Selection punya tempat jumlah nilai (batas 20 dikasih tahu, ga dipotong diam-diam)."""
    html_text = get_html(logged_in_client, "/entries/")
    assert 'data-selection-counter="include"' in html_text and 'data-selection-counter="exclude"' in html_text

def test_page_actions_live_in_toolbar(logged_in_client, registered_user, category_dict):
    """Positive: tombol khusus halaman (Edit, Hapus) pindah ke toolbar, ga di kepala halaman lagi."""
    entry = create_entry(registered_user, category_dict["Web"])
    html_text = get_html(logged_in_client, f"/entries/{entry.id}")
    toolbar_html = html_text.split('aria-label="Toolbar layar"')[1].split('id="main_content"')[0]
    assert f'href="/entries/{entry.id}/edit"' in toolbar_html
    assert 'class="app-toolbar-actions"' in toolbar_html

def test_old_buttons_removed(logged_in_client):
    """Positive: tombol Simpan/Batal lama di bawah form & tombol melayang udah ga ada (diganti toolbar)."""
    html_text = get_html(logged_in_client, "/entries/new")
    assert 'class="btn">Batal</a>' not in html_text
    assert '<button type="submit" class="btn btn-primary">' not in html_text
    assert "btn-floating" not in html_text
