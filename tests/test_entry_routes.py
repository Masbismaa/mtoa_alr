"""Test halaman data link: tambah, detail, edit, hapus, dashboard."""
import re
from app.extensions import db
from app.models import AccessEntry, AccessEntryField
from app.services.access_entry_service import create_access_entry
from tests.conftest import create_entry_as_is
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

def test_create_page_has_category_tree_for_cascade(logged_in_client, category_dict):
    """Positive: tiap pilihan kategori bawa induk + nama pendek, buat dropdown bertingkat (entry_form.js)."""
    from app.models import Category

    web = category_dict["Web"]
    sap = Category(parent_id=web.id, name="SAP", is_active=True)
    db.session.add(sap)
    db.session.commit()
    html_text = logged_in_client.get("/entries/new").get_data(as_text=True)
    assert f'value="{sap.id}" data-parent-id="{web.id}" data-name="SAP"' in html_text
    assert f'value="{web.id}" data-parent-id="" data-name="Web"' in html_text
    assert "data-category-cascade" in html_text

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
    assert "http:// or https://" in response.get_data(as_text=True)

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

def test_detail_never_embeds_access_note(logged_in_client, registered_user, category_dict):
    """Negative (security): isi access note ga pernah ada di HTML detail (diambil lewat API pas Show/Copy,
    ditampilin JS pake textContent), jadi script di dalemnya ga bisa jalan & ga kebaca dari source halaman."""
    entry = create_access_entry(registered_user, build_service_dict(
        category_dict["Web"], access_note="<script>alert(1)</script>",
    ))
    html_text = logged_in_client.get(f"/entries/{entry.id}").get_data(as_text=True)
    assert "alert(1)" not in html_text
    assert f'data-secret-url="/entries/{entry.id}/access-note"' in html_text
    api_data = logged_in_client.post(f"/entries/{entry.id}/access-note").get_json()
    assert api_data["data"]["access_note"] == "<script>alert(1)</script>"

def test_private_entry_of_other_user_returns_404(logged_in_client, other_user, category_dict):
    """Negative (security/IDOR): private orang lain dijawab 404 (keberadaannya ga bocor)."""
    entry = create_access_entry(other_user, build_service_dict(category_dict["Web"]))
    assert logged_in_client.get(f"/entries/{entry.id}").status_code == 404

def test_edit_public_entry_of_other_user_returns_403(logged_in_client, other_user, category_dict):
    """Negative (security): public orang lain cuma read-only."""
    entry = create_entry_as_is(other_user, build_service_dict(category_dict["Web"], visibility=VISIBILITY_PUBLIC))
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
    """Positive: data baru muncul di tabel Daftar Link."""
    create_access_entry(registered_user, build_service_dict(category_dict["Web"], title="Portal Absensi"))
    html_text = logged_in_client.get("/entries/?run=1").get_data(as_text=True)
    assert "Portal Absensi" in html_text
def test_create_entry_into_group(logged_in_client, registered_user, category_dict):
    """Positive: bikin link dari halaman group -> link kesimpen & langsung masuk group."""
    from app.services.group_service import create_group

    group = create_group(registered_user, {"name": "Tim"})
    response = logged_in_client.post(f"/entries/new?group_id={group.id}", data=build_form_dict(category_dict["Web"]))
    assert response.status_code == 302
    assert f"/groups/{group.id}" in response.location
    assert len(group.group_entry_list) == 1

def test_create_entry_into_group_partial_failure_is_explained(logged_in_client, registered_user, category_dict, monkeypatch):
    """Negative (temuan audit): link udah kesimpen tapi gagal masuk group (misal izin dicabut barengan) ->
    bukan error 500; user diarahin ke link-nya + dikasih tau, dan link ga kebikin dobel."""
    from app.routes import access_entry_routes
    from app.services.group_service import create_group
    from app.utils.exceptions import PermissionDeniedError

    group = create_group(registered_user, {"name": "Tim"})

    def fail_add(*args):
        raise PermissionDeniedError("Kamu belum diizinkan menambah link ke group ini")

    monkeypatch.setattr(access_entry_routes, "add_group_entry", fail_add)
    response = logged_in_client.post(f"/entries/new?group_id={group.id}", data=build_form_dict(category_dict["Web"]))
    entry_list = db.session.execute(db.select(AccessEntry)).scalars().all()
    assert len(entry_list) == 1
    assert response.status_code == 302
    assert f"/entries/{entry_list[0].id}" in response.location
    html_text = logged_in_client.get(response.location).get_data(as_text=True)
    assert "could not be added to group" in html_text

def test_create_entry_into_group_failure_keeps_back_url(logged_in_client, registered_user, category_dict, monkeypatch):
    """Positive: gagal masuk group -> detail link tetep bawa ?back, biar tombol Back balik ke tabel asal + filternya."""
    from app.routes import access_entry_routes
    from app.services.group_service import create_group
    from app.utils.exceptions import PermissionDeniedError

    group = create_group(registered_user, {"name": "Tim"})

    def fail_add(*args):
        raise PermissionDeniedError("izin dicabut")

    monkeypatch.setattr(access_entry_routes, "add_group_entry", fail_add)
    response = logged_in_client.post(
        f"/entries/new?group_id={group.id}&back=/entries/?title%3Dportal*",
        data=build_form_dict(category_dict["Web"]),
    )
    assert response.status_code == 302
    assert "back=/entries/?title%3Dportal*" in response.location

def test_form_hides_visibility_for_non_admin(logged_in_client):
    """Positive: form Add Link user biasa -> kartu Visibility ga ada, yg dikirim Private."""
    html_text = logged_in_client.get("/entries/new").get_data(as_text=True)
    assert 'value="public"' not in html_text
    assert '<input type="hidden" name="visibility" value="private">' in html_text


def test_form_keeps_old_public_value_for_non_admin(logged_in_client, registered_user, category_dict):
    """Positive: edit link Public lama punya user -> nilai Public tetep dikirim (ga keganti diem-diem)."""
    entry = create_entry_as_is(registered_user, build_service_dict(category_dict["Web"], visibility=VISIBILITY_PUBLIC))
    html_text = logged_in_client.get(f"/entries/{entry.id}/edit").get_data(as_text=True)
    assert '<input type="hidden" name="visibility" value="public">' in html_text


def test_form_shows_visibility_for_admin(admin_client):
    """Positive: admin -> pilihan Private & Public ada."""
    html_text = admin_client.get("/entries/new").get_data(as_text=True)
    assert re.search(r'<input[^>]*value="public"', html_text) and "All users can view" in html_text
