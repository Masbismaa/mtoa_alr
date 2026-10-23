"""Test arsip link: dipindah manual sama yg boleh edit, tampil paling bawah di tabel."""
from app.utils.constants import VISIBILITY_PUBLIC
from tests.test_favorit_dan_riwayat import make_entry


def test_toggle_archive_from_detail(logged_in_client, registered_user, category_dict):
    """Positive: klik Archive -> diarsip, klik Unarchive -> balik aktif."""
    entry = make_entry(registered_user, category_dict["Web"])
    html = logged_in_client.post(f"/entries/{entry.id}/archive", follow_redirects=True).get_data(as_text=True)
    assert "Moved to Archive" in html and "Unarchive" in html
    assert entry.is_archived is True
    html = logged_in_client.post(f"/entries/{entry.id}/archive", follow_redirects=True).get_data(as_text=True)
    assert "Restored from Archive" in html
    assert entry.is_archived is False


def test_archived_link_goes_below_active_links(logged_in_client, registered_user, category_dict, read_entry_table):
    """Positive: link diarsip selalu di bawah link aktif, walau lebih baru / diurut judul."""
    web = category_dict["Web"]
    make_entry(registered_user, web, "Portal A")
    archived = make_entry(registered_user, web, "Portal B")
    make_entry(registered_user, web, "Portal C")
    logged_in_client.post(f"/entries/{archived.id}/archive")
    row_list = read_entry_table(logged_in_client, "/entries/?run=1")["rows"]
    assert [row["title"] for row in row_list] == ["Portal C", "Portal A", "Portal B"]
    assert [row["is_archived"] for row in row_list] == [False, False, True]
    sorted_row_list = read_entry_table(logged_in_client, "/entries/?run=1&sort=title")["rows"]
    assert [row["title"] for row in sorted_row_list] == ["Portal A", "Portal C", "Portal B"]


def test_cannot_archive_public_link_of_other_user(logged_in_client, other_user, category_dict):
    """Negative (security): link Public orang lain bisa diliat tapi ga boleh diarsip."""
    entry = make_entry(other_user, category_dict["Web"], visibility=VISIBILITY_PUBLIC)
    assert logged_in_client.post(f"/entries/{entry.id}/archive").status_code == 403
    assert entry.is_archived is False


def test_cannot_archive_private_link_of_other_user(logged_in_client, other_user, category_dict):
    """Negative (security/IDOR): link private orang lain -> 404."""
    entry = make_entry(other_user, category_dict["Web"])
    assert logged_in_client.post(f"/entries/{entry.id}/archive").status_code == 404
