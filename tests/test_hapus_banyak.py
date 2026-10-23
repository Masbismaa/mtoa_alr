"""Test hapus banyak link (admin, centang di tabel Link List)."""
from app.extensions import db
from app.models import AccessEntry, AuditLog
from app.services.access_entry_service import create_access_entry
from tests.conftest import create_entry_as_is
from app.services.attachment_service import get_stored_file_path
from app.utils.constants import AUDIT_ACTION_DELETE, BULK_DELETE_MAX_COUNT, VISIBILITY_PUBLIC
from tests.test_entry_routes import build_service_dict

API_URL = "/entries/bulk-delete"


def make_entry(user, category, title, **override_dict):
    return create_entry_as_is(user, build_service_dict(
        category, title=title, url=f"https://{title.lower().replace(' ', '-')}.spindo.com", **override_dict,
    ))


def remaining_title_list():
    return sorted(db.session.execute(db.select(AccessEntry.title)).scalars())


def test_admin_deletes_selected_links_and_each_is_audited(admin_client, admin_user, registered_user, category_dict,
                                                          make_file_storage, sample_file_dict):
    """Positive: admin hapus link sendiri + link Public orang lain sekaligus; lampiran ikut kehapus, tiap link kecatat."""
    web = category_dict["Web"]
    own = create_access_entry(admin_user, build_service_dict(web, title="Punya Admin", url="https://admin.spindo.com"),
                              upload_file_list=[make_file_storage(sample_file_dict["png"], "foto.png")])
    other_public = make_entry(registered_user, web, "Public Orang", visibility=VISIBILITY_PUBLIC)
    make_entry(registered_user, web, "Tetap Ada", visibility=VISIBILITY_PUBLIC)
    stored_path = get_stored_file_path(own.attachment_list[0].stored_filename)

    response = admin_client.post(API_URL, json={"entry_id_list": [own.id, other_public.id]})
    assert response.status_code == 200
    assert response.get_json()["data"]["deleted_count"] == 2
    assert remaining_title_list() == ["Tetap Ada"]
    assert not stored_path.exists()
    audit_id_list = db.session.execute(
        db.select(AuditLog.entity_id).filter_by(action=AUDIT_ACTION_DELETE, entity_type="access_entries")
    ).scalars().all()
    assert sorted(audit_id_list) == sorted([str(own.id), str(other_public.id)])


def test_private_link_of_other_user_is_skipped(admin_client, registered_user, category_dict):
    """Negative (security): link Private orang lain ga ikut kehapus walau id-nya dikirim (admin ga boleh liat)."""
    private_entry = make_entry(registered_user, category_dict["Web"], "Private Orang")
    response = admin_client.post(API_URL, json={"entry_id_list": [private_entry.id]})
    assert response.get_json()["data"]["deleted_count"] == 0
    assert remaining_title_list() == ["Private Orang"]


def test_non_admin_cannot_bulk_delete(logged_in_client, registered_user, category_dict):
    """Negative (security): user biasa ditolak, walau link-nya punya sendiri."""
    entry = make_entry(registered_user, category_dict["Web"], "Punya Sendiri")
    response = logged_in_client.post(API_URL, json={"entry_id_list": [entry.id]})
    assert response.status_code == 403
    assert remaining_title_list() == ["Punya Sendiri"]


def test_bulk_delete_rejects_bad_input(admin_client):
    """Negative: kosong, kebanyakan, bukan angka, bukan JSON -> 400."""
    for body in ({"entry_id_list": []}, {"entry_id_list": list(range(1, BULK_DELETE_MAX_COUNT + 2))},
                 {"entry_id_list": ["abc"]}, {"entry_id_list": "1,2"}, ["1"]):
        assert admin_client.post(API_URL, json=body).status_code == 400


def test_bulk_delete_requires_login(client):
    """Negative: belum login -> 401 JSON."""
    assert client.post(API_URL, json={"entry_id_list": [1]}).status_code == 401


def test_table_payload_marks_deletable_rows_for_admin(admin_client, admin_user, category_dict, read_entry_table):
    """Positive: admin dapet URL hapus banyak & tanda baris yg boleh dicentang."""
    make_entry(admin_user, category_dict["Web"], "Punya Admin")
    payload = read_entry_table(admin_client, "/entries/?run=1")
    assert payload["bulk_delete_url"] == API_URL
    assert [row["can_delete"] for row in payload["rows"]] == [True]


def test_table_payload_has_no_bulk_delete_for_regular_user(logged_in_client, registered_user, category_dict, read_entry_table):
    """Negative: user biasa ga dapet kolom centang sama sekali, walau link-nya punya sendiri."""
    make_entry(registered_user, category_dict["Web"], "Punya Sendiri")
    payload = read_entry_table(logged_in_client, "/entries/?run=1")
    assert payload["bulk_delete_url"] is None
    assert [row["can_delete"] for row in payload["rows"]] == [False]
