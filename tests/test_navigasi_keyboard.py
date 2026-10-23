"""Test navigasi keyboard ala SAP: baris aktif bisa dibuka (data-row-url), shortcut di toolbar & panel, daftar shortcut di Bantuan."""
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
    """Positive: baris Daftar Link (tabel React) bawa alamat detail (plus alamat tabel asal) buat Enter / double-click."""
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
    """Positive: script baris aktif & shortcut kepasang di layar aplikasi (shortcut F-key dijalanin app_shell.js)."""
    html_text = get_html(logged_in_client, "/entries/")
    assert "js/components/table_row.js" in html_text and "js/components/app_shell.js" in html_text

# SHORTCUT
def test_toolbar_shortcut_marks(logged_in_client, registered_user, category_dict):
    """Positive: tombol toolbar ditandain shortcut SAP + kelihatan di tooltip."""
    entry = create_entry(registered_user, category_dict["Web"], "Portal HR")
    html_text = get_html(logged_in_client, f"/entries/{entry.id}/edit")
    assert 'title="Back to the previous screen (F3)" data-fkey="F3"' in html_text
    assert 'title="Exit this screen to the Dashboard (Shift+F3)" data-fkey="Shift+F3"' in html_text
    assert 'data-fkey="F12" aria-keyshortcuts="F12"' in html_text
    assert 'title="Save changes (Ctrl+S)" data-fkey="Ctrl+S"' in html_text
    assert 'data-fkey="F1" aria-keyshortcuts="F1"' in html_text

def test_disabled_toolbar_button_has_no_shortcut(logged_in_client):
    """Negative: tombol yg nonaktif di layar ini ga ditandain shortcut (jadi F12/Ctrl+S ga ngapa-ngapain)."""
    html_text = get_html(logged_in_client, "/entries/")
    assert 'data-fkey="F12"' not in html_text and 'data-fkey="Ctrl+S"' not in html_text

def test_run_shortcut_on_selection_panel(logged_in_client):
    """Positive: tombol Execute di Kriteria Pencarian bisa dipanggil F8."""
    assert 'data-fkey="F8" aria-keyshortcuts="F8" title="Execute (F8)"' in get_html(logged_in_client, "/entries/")

def test_help_lists_shortcuts(logged_in_client):
    """Positive: Bantuan nampilin daftar shortcut keyboard."""
    help_html = get_html(logged_in_client, "/entries/").split('id="help_dialog"')[1]
    for key_text in ["F3", "Shift+F3", "F12", "Ctrl+S", "F8", "F1", "Shift+F10"]:
        assert f"<kbd>{key_text}</kbd>" in help_html
