"""Test buka/copy password (access note): cuma yg berhak bisa buka, & ga dicatat di audit log."""
from app.config import TestingConfig
from app.extensions import db
from app.models import AuditLog
from app.services.access_entry_service import create_access_entry
from tests.conftest import create_entry_as_is
from app.utils.constants import VISIBILITY_PUBLIC
from tests.test_entry_routes import build_service_dict

SECRET = "SandiRahasia123"


def make_entry(user, category, **override_dict):
    return create_entry_as_is(user, build_service_dict(category, access_note=SECRET, **override_dict))


def reveal_log_list():
    """Catatan audit selain pembuatan link (yg dibuat make_entry): harusnya kosong kalau cuma buka password."""
    return db.session.execute(
        db.select(AuditLog).where(AuditLog.entity_type == "access_entries", AuditLog.action != "create")
    ).scalars().all()


def test_reveal_returns_note_and_is_not_audited(logged_in_client, registered_user, category_dict):
    """Positive: Show/Copy -> isi password kebuka, ga nambah catatan audit."""
    entry = make_entry(registered_user, category_dict["Web"])
    response = logged_in_client.post(f"/entries/{entry.id}/access-note")
    assert response.status_code == 200
    assert response.get_json()["data"]["access_note"] == SECRET
    assert "no-store" in response.headers["Cache-Control"]
    assert reveal_log_list() == []


def test_opening_detail_page_alone_is_not_logged(logged_in_client, registered_user, category_dict):
    """Positive: cuma buka halaman detail (password masih ditutup) ga dihitung buka password."""
    entry = make_entry(registered_user, category_dict["Web"])
    assert logged_in_client.get(f"/entries/{entry.id}").status_code == 200
    assert reveal_log_list() == []


def test_public_link_of_other_user_can_be_revealed(logged_in_client, registered_user, other_user, category_dict):
    """Positive: link Public punya orang lain boleh dibuka (kayak sebelumnya), ga dicatat."""
    entry = make_entry(other_user, category_dict["Web"], visibility=VISIBILITY_PUBLIC)
    assert logged_in_client.post(f"/entries/{entry.id}/access-note").status_code == 200
    assert reveal_log_list() == []


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


def test_edit_form_showing_note_is_not_logged(logged_in_client, registered_user, category_dict):
    """Positive: form edit keisi password-nya, ga dicatat."""
    entry = make_entry(registered_user, category_dict["Web"])
    response = logged_in_client.get(f"/entries/{entry.id}/edit")
    assert response.status_code == 200
    assert SECRET in response.get_data(as_text=True)
    assert reveal_log_list() == []
