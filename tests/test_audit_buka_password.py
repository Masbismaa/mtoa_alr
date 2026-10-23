"""Test buka/copy password (access note) kecatat di audit: siapa buka password link apa, kapan."""
from app.config import TestingConfig
from app.extensions import db
from app.models import AuditLog
from app.services.access_entry_service import create_access_entry
from tests.conftest import create_entry_as_is
from app.utils.constants import AUDIT_ACTION_REVEAL, VISIBILITY_PUBLIC
from tests.test_entry_routes import build_service_dict

SECRET = "SandiRahasia123"


def make_entry(user, category, **override_dict):
    return create_entry_as_is(user, build_service_dict(category, access_note=SECRET, **override_dict))


def reveal_log_list():
    return db.session.execute(db.select(AuditLog).filter_by(action=AUDIT_ACTION_REVEAL)).scalars().all()


def test_reveal_returns_note_and_is_audited_without_the_secret(logged_in_client, registered_user, category_dict):
    """Positive: Show/Copy -> isi password kebuka & kecatat (link, pelaku), tapi password-nya sendiri ga ikut kecatat."""
    entry = make_entry(registered_user, category_dict["Web"])
    response = logged_in_client.post(f"/entries/{entry.id}/access-note")
    assert response.status_code == 200
    assert response.get_json()["data"]["access_note"] == SECRET
    assert "no-store" in response.headers["Cache-Control"]
    log_list = reveal_log_list()
    assert [(log.entity_type, log.entity_id, log.actor_email) for log in log_list] == [
        ("access_entries", str(entry.id), registered_user.email),
    ]
    assert SECRET not in str(log_list[0].old_data) + str(log_list[0].new_data)


def test_opening_detail_page_alone_is_not_logged(logged_in_client, registered_user, category_dict):
    """Positive: cuma buka halaman detail (password masih ditutup) ga dihitung buka password."""
    entry = make_entry(registered_user, category_dict["Web"])
    assert logged_in_client.get(f"/entries/{entry.id}").status_code == 200
    assert reveal_log_list() == []


def test_public_link_reveal_by_other_user_is_logged_as_that_user(logged_in_client, registered_user, other_user, category_dict):
    """Positive: link Public punya orang lain boleh dibuka (kayak sebelumnya), yg kecatat yg buka, bukan pemiliknya."""
    entry = make_entry(other_user, category_dict["Web"], visibility=VISIBILITY_PUBLIC)
    assert logged_in_client.post(f"/entries/{entry.id}/access-note").status_code == 200
    assert [log.actor_email for log in reveal_log_list()] == [registered_user.email]


def test_private_link_of_other_user_cannot_be_revealed(logged_in_client, other_user, category_dict):
    """Negative (security/IDOR): private orang lain -> 404, password ga keluar, ga ada catatan."""
    entry = make_entry(other_user, category_dict["Web"])
    response = logged_in_client.post(f"/entries/{entry.id}/access-note")
    assert response.status_code == 404
    assert SECRET not in response.get_data(as_text=True)
    assert reveal_log_list() == []


def test_link_without_note_returns_404_and_is_not_logged(logged_in_client, registered_user, category_dict):
    """Negative: link tanpa access note -> 404, ga dicatat."""
    entry = create_access_entry(registered_user, build_service_dict(category_dict["Web"]))
    assert logged_in_client.post(f"/entries/{entry.id}/access-note").status_code == 404
    assert reveal_log_list() == []


def test_reveal_requires_login(client, registered_user, category_dict):
    """Negative (security): belum login -> 401 JSON, password ga keluar."""
    entry = make_entry(registered_user, category_dict["Web"])
    response = client.post(f"/entries/{entry.id}/access-note")
    assert response.status_code == 401
    assert SECRET not in response.get_data(as_text=True)


def test_reveal_requires_csrf_token(monkeypatch, registered_user, category_dict):
    """Negative (security): POST tanpa token CSRF ditolak (situs lain ga bisa nyuruh browser user buka password)."""
    from app import create_app

    monkeypatch.setattr(TestingConfig, "WTF_CSRF_ENABLED", True)
    csrf_app = create_app("testing")
    with csrf_app.app_context():
        db.create_all()
        response = csrf_app.test_client().post("/entries/1/access-note")
        assert response.status_code == 400
        db.drop_all()


def test_edit_form_showing_note_is_logged(logged_in_client, registered_user, category_dict):
    """Positive: buka form edit (password keisi di form) juga kecatat sebagai buka password."""
    entry = make_entry(registered_user, category_dict["Web"])
    assert logged_in_client.get(f"/entries/{entry.id}/edit").status_code == 200
    assert len(reveal_log_list()) == 1
    plain_entry = create_access_entry(registered_user, build_service_dict(category_dict["Web"], url="https://lain2.spindo.com"))
    logged_in_client.get(f"/entries/{plain_entry.id}/edit")
    assert len(reveal_log_list()) == 1
