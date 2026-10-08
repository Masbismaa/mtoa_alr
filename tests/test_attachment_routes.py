"""Test lampiran lewat halaman: upload dari form & download."""
import io

from app.extensions import db
from app.models import AccessEntry, Attachment
from app.services.access_entry_service import create_access_entry
from app.utils.constants import VISIBILITY_PRIVATE

def build_service_dict(category, **override_dict):
    """Helper: data link buat dibikin langsung lewat service."""
    service_dict = {
        "category_id": category.id, "title": "Server File", "url": "https://file.spindo.com",
        "address": "", "port": "", "username": "", "access_note": "", "description": "",
        "visibility": VISIBILITY_PRIVATE,
    }
    service_dict.update(override_dict)
    return service_dict

def test_upload_attachment_via_form(logged_in_client, category_dict, sample_file_dict):
    """Positive: upload dari form tambah link."""
    response = logged_in_client.post(
        "/entries/new",
        data={
            "category_id": str(category_dict["Web"].id),
            "title": "Printer Lt 3",
            "url": "https://printer.spindo.com",
            "visibility": VISIBILITY_PRIVATE,
            "attachments": (io.BytesIO(sample_file_dict["png"]), "foto printer.png"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 302
    assert db.session.execute(db.select(db.func.count(Attachment.id))).scalar() == 1

def test_invalid_file_via_form_shows_error(logged_in_client, category_dict, sample_file_dict):
    """Negative (security): file palsu ditolak, form nampilin error, data ga kesimpen."""
    response = logged_in_client.post(
        "/entries/new",
        data={
            "category_id": str(category_dict["Web"].id),
            "title": "Tagihan",
            "url": "https://tagihan.spindo.com",
            "visibility": VISIBILITY_PRIVATE,
            "attachments": (io.BytesIO(sample_file_dict["exe"]), "tagihan.pdf"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert "tidak sesuai" in response.get_data(as_text=True)
    assert db.session.execute(db.select(db.func.count(AccessEntry.id))).scalar() == 0

def test_download_own_attachment(logged_in_client, registered_user, category_dict, sample_file_dict, make_file_storage):
    """Positive: download lampiran sendiri, selalu sebagai file + header aman."""
    entry = create_access_entry(
        registered_user, build_service_dict(category_dict["Web"]),
        upload_file_list=[make_file_storage(sample_file_dict["txt"], "catatan.txt")],
    )
    response = logged_in_client.get(f"/attachments/{entry.attachment_list[0].id}")
    assert response.status_code == 200
    assert "attachment" in response.headers["Content-Disposition"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.data == sample_file_dict["txt"]
    response.close()

def test_download_private_attachment_of_other_user_returns_404(logged_in_client, other_user, category_dict, sample_file_dict, make_file_storage):
    """Negative (security/IDOR): lampiran di data private orang lain -> 404."""
    entry = create_access_entry(
        other_user, build_service_dict(category_dict["Web"]),
        upload_file_list=[make_file_storage(sample_file_dict["png"], "rahasia.png")],
    )
    assert logged_in_client.get(f"/attachments/{entry.attachment_list[0].id}").status_code == 404

def test_download_requires_login(client):
    """Negative (security): belum login ga bisa download."""
    response = client.get("/attachments/1")
    assert response.status_code == 302
    assert "/auth/login" in response.location

def test_detail_page_lists_attachment(logged_in_client, registered_user, category_dict, sample_file_dict, make_file_storage):
    """Positive: nama lampiran muncul di halaman detail."""
    entry = create_access_entry(
        registered_user, build_service_dict(category_dict["Web"]),
        upload_file_list=[make_file_storage(sample_file_dict["pdf"], "panduan akses.pdf")],
    )
    html_text = logged_in_client.get(f"/entries/{entry.id}").get_data(as_text=True)
    assert "panduan akses.pdf" in html_text
    assert "Download" in html_text