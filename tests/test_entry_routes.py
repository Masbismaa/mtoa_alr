"""Test halaman data link: tambah, detail, edit, hapus, dashboard."""
from app.extensions import db
from app.models import AccessEntry, AccessEntryField
from app.services.access_entry_service import create_access_entry
from app.utils.constants import VISIBILITY_PRIVATE, VISIBILITY_PUBLIC

def build_form_dict(category, **override_dict):
    """Helper: isi form data link."""
    form_dict = {
        "category_id": str(category.id),
        "title": "Portal Finance",
        "url": "https://finance.spindo.com",
        "visibility": VISIBILITY_PRIVATE,
    }
    form_dict.update(override_dict)
    return form_dict

def build_service_dict(category, **override_dict):
    """Helper: data buat bikin entry langsung lewat service."""
    service_dict = {
        "category_id": category.id, "title": "Data Lain", "url": "https://lain.spindo.com",
        "address": "", "port": "", "username": "", "access_note": "", "description": "",
        "visibility": VISIBILITY_PRIVATE,
    }
    service_dict.update(override_dict)
    return service_dict

def test_entry_pages_require_login(client):
    """Negative (security): belum login ga bisa buka form."""
    response = client.get("/entries/new")
    assert response.status_code == 302
    assert "/auth/login" in response.location

def test_create_page_loads_with_categories(logged_in_client, category_dict):
    """Positive: form kebuka, ada pilihan General & tombol Add field."""
    html_text = logged_in_client.get("/entries/new").get_data(as_text=True)
    assert "General" in html_text
    assert "Add field" in html_text

def test_create_web_entry_via_form(logged_in_client, category_dict):
    """Positive: simpan -> diarahin ke detail."""
    response = logged_in_client.post("/entries/new", data=build_form_dict(category_dict["Web"]))
    assert response.status_code == 302
    assert "/entries/" in response.location
    detail_text = logged_in_client.get(response.location).get_data(as_text=True)
    assert "Portal Finance" in detail_text

def test_create_invalid_url_shows_error(logged_in_client, category_dict):
    """Negative: URL ftp ditolak, pesan error muncul di form."""
    response = logged_in_client.post("/entries/new", data=build_form_dict(category_dict["Web"], url="ftp://files.spindo.com"))
    assert response.status_code == 200
    assert "http:// atau https://" in response.get_data(as_text=True)

def test_create_general_entry_with_custom_fields(logged_in_client, category_dict):
    """Positive (revisi): field tambahan dari form kesimpen sesuai urutan."""
    form_dict = build_form_dict(
        category_dict["General"],
        title="Panduan Printer",
        custom_field_label=["Lokasi", "Cara pakai"],
        custom_field_content=["<p>Lantai 2</p>", "<ol><li>Nyalain</li></ol>"],
    )
    response = logged_in_client.post("/entries/new", data=form_dict)
    assert response.status_code == 302
    assert db.session.execute(db.select(db.func.count(AccessEntryField.id))).scalar() == 2

def test_detail_escapes_access_note(logged_in_client, registered_user, category_dict):
    """Negative (security): access note berisi script tampil sebagai teks, ga dijalanin."""
    entry = create_access_entry(registered_user, build_service_dict(
        category_dict["Web"], access_note="<script>alert(1)</script>",
    ))
    html_text = logged_in_client.get(f"/entries/{entry.id}").get_data(as_text=True)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_text
    assert "<script>alert(1)" not in html_text

def test_private_entry_of_other_user_returns_404(logged_in_client, other_user, category_dict):
    """Negative (security/IDOR): private orang lain dijawab 404 (keberadaannya ga bocor)."""
    entry = create_access_entry(other_user, build_service_dict(category_dict["Web"]))
    assert logged_in_client.get(f"/entries/{entry.id}").status_code == 404

def test_edit_public_entry_of_other_user_returns_403(logged_in_client, other_user, category_dict):
    """Negative (security): public orang lain cuma read-only."""
    entry = create_access_entry(other_user, build_service_dict(category_dict["Web"], visibility=VISIBILITY_PUBLIC))
    assert logged_in_client.get(f"/entries/{entry.id}/edit").status_code == 403
    assert logged_in_client.post(f"/entries/{entry.id}/delete").status_code == 403

def test_delete_entry_via_post(logged_in_client, registered_user, category_dict):
    """Positive: hapus -> balik ke dashboard, datanya ilang."""
    entry = create_access_entry(registered_user, build_service_dict(category_dict["Web"]))
    entry_id = entry.id
    response = logged_in_client.post(f"/entries/{entry_id}/delete")
    assert response.status_code == 302
    assert db.session.get(AccessEntry, entry_id) is None

def test_dashboard_shows_entry(logged_in_client, registered_user, category_dict):
    """Positive: data baru muncul di tabel dashboard."""
    create_access_entry(registered_user, build_service_dict(category_dict["Web"], title="Portal Absensi"))
    html_text = logged_in_client.get("/").get_data(as_text=True)
    assert "Portal Absensi" in html_text