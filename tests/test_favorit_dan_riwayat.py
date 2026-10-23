"""Test favorit (bintang) link & riwayat per link di halaman detail."""
from app.extensions import db
from app.models import UserFavorite
from app.services.access_entry_service import create_access_entry, delete_access_entry, update_access_entry
from app.utils.constants import VISIBILITY_PRIVATE, VISIBILITY_PUBLIC
from tests.conftest import create_entry_as_is
from tests.test_entry_routes import build_service_dict


def make_entry(user, category, title="Portal HR", **override_dict):
    return create_entry_as_is(user, build_service_dict(category, title=title, url=f"https://{title.lower().replace(' ', '')}.spindo.com", **override_dict))


def count_favorite():
    return db.session.execute(db.select(db.func.count(UserFavorite.id))).scalar()


# FAVORIT

def test_toggle_favorite_from_detail(logged_in_client, registered_user, category_dict):
    """Positive: klik bintang -> masuk favorit, klik lagi -> keluar."""
    entry = make_entry(registered_user, category_dict["Web"])
    response = logged_in_client.post(f"/entries/{entry.id}/favorite", follow_redirects=True)
    assert "Added to Favorites" in response.get_data(as_text=True) and "Remove from Favorites" in response.get_data(as_text=True)
    assert count_favorite() == 1
    response = logged_in_client.post(f"/entries/{entry.id}/favorite", follow_redirects=True)
    assert "Removed from Favorites" in response.get_data(as_text=True)
    assert count_favorite() == 0


def test_favorites_filter_shows_only_my_favorites(logged_in_client, registered_user, other_user, category_dict, read_entry_table):
    """Positive: Link List ?favorite=1 cuma isi link yg dibintangin user ini (bintang orang lain ga ikut)."""
    web = category_dict["Web"]
    starred = make_entry(registered_user, web, "Portal A")
    make_entry(registered_user, web, "Portal B")
    shared = make_entry(other_user, web, "Portal C", visibility=VISIBILITY_PUBLIC)
    logged_in_client.post(f"/entries/{starred.id}/favorite")
    db.session.add(UserFavorite(user_id=other_user.id, access_entry_id=shared.id))
    db.session.commit()
    payload = read_entry_table(logged_in_client, "/entries/?favorite=1")
    assert [row["title"] for row in payload["rows"]] == ["Portal A"]


def test_favorite_of_link_that_became_private_disappears(logged_in_client, registered_user, other_user, category_dict, read_entry_table):
    """Negative (security): bintangin link Public orang, terus pemiliknya bikin Private -> ga muncul lagi & ga bisa dibuka."""
    entry = make_entry(other_user, category_dict["Web"], visibility=VISIBILITY_PUBLIC)
    logged_in_client.post(f"/entries/{entry.id}/favorite")
    update_access_entry(other_user, entry, build_service_dict(category_dict["Web"], title="Portal HR",
                                                              url="https://portalhr.spindo.com", visibility=VISIBILITY_PRIVATE))
    payload = read_entry_table(logged_in_client, "/entries/?favorite=1")
    assert payload["rows"] == []
    assert logged_in_client.get(f"/entries/{entry.id}").status_code == 404


def test_cannot_favorite_private_link_of_other_user(logged_in_client, other_user, category_dict):
    """Negative (security/IDOR): link private orang lain -> 404, ga ada baris favorit."""
    entry = make_entry(other_user, category_dict["Web"])
    assert logged_in_client.post(f"/entries/{entry.id}/favorite").status_code == 404
    assert count_favorite() == 0


def test_deleting_link_removes_its_favorites(logged_in_client, registered_user, category_dict):
    """Positive: link dihapus -> favoritnya ikut kehapus (ga nyisa baris yatim)."""
    entry = make_entry(registered_user, category_dict["Web"])
    logged_in_client.post(f"/entries/{entry.id}/favorite")
    delete_access_entry(registered_user, entry)
    assert count_favorite() == 0


def test_sidebar_has_favorites_menu(logged_in_client):
    """Positive: menu Links > Favorites ada di sidebar."""
    assert 'href="/entries/?favorite=1"' in logged_in_client.get("/").get_data(as_text=True)


def test_favorite_requires_login(client, registered_user, category_dict):
    """Negative: belum login ga bisa nandain."""
    entry = make_entry(registered_user, category_dict["Web"])
    assert "/auth/login" in client.post(f"/entries/{entry.id}/favorite").location


# RIWAYAT PER LINK

def test_owner_sees_history_with_changes(logged_in_client, registered_user, category_dict):
    """Positive: pemilik liat riwayat link: dibuat & diubah (field apa). Buka password ga masuk riwayat, isinya ga ikut."""
    entry = make_entry(registered_user, category_dict["Web"], access_note="SandiRahasia123")
    update_access_entry(registered_user, entry, build_service_dict(category_dict["Web"], title="Portal HR Baru",
                                                                   url="https://portalhr.spindo.com", access_note="SandiRahasia123"))
    logged_in_client.post(f"/entries/{entry.id}/access-note")
    html_text = logged_in_client.get(f"/entries/{entry.id}").get_data(as_text=True)
    history_html = html_text.split("entry-history", 1)[1]
    assert "Create" in history_html and "Change" in history_html and "reveal" not in history_html.lower()
    assert "Changed: title" in history_html
    assert registered_user.email in history_html
    assert "SandiRahasia123" not in html_text


def test_viewer_without_edit_access_does_not_see_history(logged_in_client, other_user, category_dict):
    """Negative: link Public orang lain (ga punya izin edit) -> kartu History ga ada."""
    entry = make_entry(other_user, category_dict["Web"], visibility=VISIBILITY_PUBLIC)
    html_text = logged_in_client.get(f"/entries/{entry.id}").get_data(as_text=True)
    assert "entry-history" not in html_text and "No history yet." not in html_text
