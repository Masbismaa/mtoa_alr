"""Test baris tabel bisa dibuka (data-row-url, double-click) & shortcut keyboard udah dihapus total."""
from app.services.access_entry_service import create_access_entry
from app.services.audit_service import log_audit
from app.utils.constants import AUDIT_ACTION_LOGIN_FAILED, VISIBILITY_PRIVATE

def create_entry(user, category, title):
    """Helper: bikin link contoh, URL-nya beda tiap judul (URL dobel ditolak)."""
    return create_access_entry(user, {
        "category_id": category.id, "title": title, "url": f"https://{title.lower().replace(' ', '-')}.spindo.com",
        "address": "", "port": "", "username": "", "access_note": "", "description": "", "visibility": VISIBILITY_PRIVATE,
    })

def get_html(client, url):
    """Helper: isi halaman."""
    return client.get(url).get_data(as_text=True)

# BARIS AKTIF
def test_entry_row_opens_detail(logged_in_client, registered_user, category_dict):
    """Positive: baris Daftar Link (tabel React) bawa alamat detail (plus alamat tabel asal) buat double-click."""
    entry = create_entry(registered_user, category_dict["Web"], "Portal HR")
    html_text = get_html(logged_in_client, "/entries/?run=1")
    assert f'"detail_url": "/entries/{entry.id}?back=/entries/?run%3D1%23daftar_link"' in html_text

def test_audit_row_opens_detail(admin_client):
    """Positive: baris Audit Logs kebuka ke detail catatannya."""
    audit_log = log_audit(AUDIT_ACTION_LOGIN_FAILED, "users", actor_email="penyusup@luar.com", is_commit=True)
    assert f'<tr data-row-url="/audit-logs/{audit_log.id}">' in get_html(admin_client, "/audit-logs/")

def test_user_row_has_no_access_link(admin_client, registered_user):
    """Negative: halaman Atur Akses udah dihapus -> baris tabel user ga ngarah ke sana lagi."""
    html_text = get_html(admin_client, "/users/")
    assert registered_user.email in html_text
    assert "/access" not in html_text

def test_row_script_loaded(logged_in_client):
    """Positive: script baris aktif (klik / double-click / klik kanan) kepasang di layar aplikasi."""
    assert "js/components/table_row.js" in get_html(logged_in_client, "/entries/")

# SHORTCUT (udah dihapus total)
def test_no_keyboard_shortcut_left(logged_in_client, registered_user, category_dict):
    """Negative: tombol toolbar, Execute, Delete, menu bar & Help ga bawa shortcut keyboard lagi."""
    entry = create_entry(registered_user, category_dict["Web"], "Portal HR")
    for url in (f"/entries/{entry.id}/edit", f"/entries/{entry.id}", "/entries/"):
        html_text = get_html(logged_in_client, url)
        for marker in ("data-fkey", "aria-keyshortcuts", "accesskey", "<kbd", "(F3)", "(F8)", "(F1)", "Ctrl+S", "Shift+F", "press /"):
            assert marker not in html_text, (url, marker)

def test_help_lists_toolbar_buttons_without_keys(logged_in_client):
    """Positive: Bantuan tetap jelasin fungsi tombol toolbar, tanpa daftar tombol keyboard."""
    help_html = get_html(logged_in_client, "/entries/").split('id="help_dialog"')[1].split("</dialog>")[0]
    for label in ["Back", "Exit", "Cancel", "Save", "Execute", "Delete", "Find"]:
        assert f"<dt>{label}</dt>" in help_html
    assert "<kbd>" not in help_html
