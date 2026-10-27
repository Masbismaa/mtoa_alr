"""Test hak admin: CRUD semua link Public, dan liat link Private orang lain (read-only): detail, daftar, access note kebuka,
tapi ubah / arsip / hapus / bagiin ke group tetep ditolak."""
from app.extensions import db
from app.models import AccessEntry
from app.utils.constants import VISIBILITY_PRIVATE, VISIBILITY_PUBLIC
from tests.conftest import create_entry_as_is
from tests.test_entry_routes import build_form_dict, build_service_dict
from tests.test_entry_table_api import API_URL, get_api_data

SECRET = "SandiRahasia123"


def make_private_entry(owner, category):
    return create_entry_as_is(owner, build_service_dict(
        category, title="VPN Rahasia", url="https://vpn.spindo.com", access_note=SECRET, visibility=VISIBILITY_PRIVATE,
    ))


def test_admin_sees_private_entry_of_other_user(admin_client, registered_user, category_dict):
    """Positive: detail kebuka tanpa tombol ubah, access note bisa dibuka, link ikut di daftar."""
    entry = make_private_entry(registered_user, category_dict["Web"])
    response = admin_client.get(f"/entries/{entry.id}")
    assert response.status_code == 200
    html_text = response.get_data(as_text=True)
    assert "VPN Rahasia" in html_text and f"/entries/{entry.id}/edit" not in html_text
    reveal = admin_client.post(f"/entries/{entry.id}/access-note")
    assert reveal.status_code == 200 and reveal.get_json()["data"]["access_note"] == SECRET
    titles = {row["title"] for row in get_api_data(admin_client, API_URL + "?run=1")["rows"]}
    assert "VPN Rahasia" in titles


def test_admin_cannot_change_private_entry_of_other_user(admin_client, registered_user, category_dict):
    """Negative (security): ubah / arsip / hapus / hapus banyak link Private orang lain ditolak, datanya utuh."""
    entry = make_private_entry(registered_user, category_dict["Web"])
    assert admin_client.get(f"/entries/{entry.id}/edit").status_code == 403
    assert admin_client.post(f"/entries/{entry.id}/edit", data=build_form_dict(category_dict["Web"])).status_code == 403
    assert admin_client.post(f"/entries/{entry.id}/archive").status_code == 403
    assert admin_client.post(f"/entries/{entry.id}/delete").status_code == 403
    bulk_response = admin_client.post("/entries/bulk-delete", json={"entry_id_list": [entry.id]})
    assert bulk_response.get_json()["data"]["deleted_count"] == 0
    db.session.expire_all()
    saved_entry = db.session.get(AccessEntry, entry.id)
    assert saved_entry is not None and saved_entry.title == "VPN Rahasia" and saved_entry.is_archived is False


def test_admin_not_blocked_by_duplicate_in_private_of_other_user(admin_client, registered_user, category_dict):
    """Positive: URL yg sama di link Private orang lain ga bikin admin dianggap duplikat."""
    make_private_entry(registered_user, category_dict["Web"])
    response = admin_client.post("/entries/new", data=build_form_dict(category_dict["Web"], url="https://vpn.spindo.com"))
    assert response.status_code == 302


def test_regular_user_still_cannot_see_private_of_other_user(logged_in_client, other_user, category_dict):
    """Negative (security): user biasa tetep ga bisa liat / buka access note link Private orang lain."""
    entry = make_private_entry(other_user, category_dict["Web"])
    assert logged_in_client.get(f"/entries/{entry.id}").status_code == 404
    assert logged_in_client.post(f"/entries/{entry.id}/access-note").status_code == 404


def test_admin_crud_public_entry_of_other_user(admin_client, registered_user, category_dict):
    """Positive: admin bisa bikin link Public, dan ubah / arsip / hapus link Public punya user lain."""
    created = admin_client.post("/entries/new", data=build_form_dict(
        category_dict["Web"], title="Portal Admin", url="https://admin-portal.spindo.com", visibility=VISIBILITY_PUBLIC))
    assert created.status_code == 302
    assert db.session.execute(db.select(AccessEntry).filter_by(title="Portal Admin")).scalar_one().visibility == VISIBILITY_PUBLIC

    entry = create_entry_as_is(registered_user, build_service_dict(
        category_dict["Web"], title="Portal Umum", url="https://umum.spindo.com", visibility=VISIBILITY_PUBLIC))
    entry_id = entry.id
    updated = admin_client.post(f"/entries/{entry_id}/edit", data=build_form_dict(
        category_dict["Web"], title="Portal Umum Baru", url="https://umum.spindo.com", visibility=VISIBILITY_PUBLIC))
    assert updated.status_code == 302
    assert admin_client.post(f"/entries/{entry_id}/archive").status_code == 302
    db.session.expire_all()
    saved_entry = db.session.get(AccessEntry, entry_id)
    assert saved_entry.title == "Portal Umum Baru" and saved_entry.is_archived is True
    assert admin_client.post(f"/entries/{entry_id}/delete").status_code == 302
    db.session.expire_all()
    assert db.session.get(AccessEntry, entry_id) is None
