"""Test aturan hak akses data link (SR-04)."""

from app.models import AccessEntry
from app.security.access_policy import can_edit_entry, can_view_entry
from app.utils.constants import VISIBILITY_PRIVATE, VISIBILITY_PUBLIC


def build_entry(owner, visibility):
    """Helper: objek entry contoh (ga perlu disimpen ke DB)."""
    return AccessEntry(user_id=owner.id, visibility=visibility)


def test_owner_can_view_and_edit_private(registered_user):
    """Positive: pemilik bebas liat & ubah data private-nya."""
    entry = build_entry(registered_user, VISIBILITY_PRIVATE)
    assert can_view_entry(registered_user, entry) is True
    assert can_edit_entry(registered_user, entry) is True


def test_other_user_can_view_public_but_not_edit(registered_user, other_user):
    """Positive & negative: public orang lain cuma bisa dilihat (read-only)."""
    entry = build_entry(other_user, VISIBILITY_PUBLIC)
    assert can_view_entry(registered_user, entry) is True
    assert can_edit_entry(registered_user, entry) is False


def test_other_user_cannot_view_private(registered_user, other_user):
    """Negative (security): private orang lain ga keliatan sama sekali."""
    entry = build_entry(other_user, VISIBILITY_PRIVATE)
    assert can_view_entry(registered_user, entry) is False
    assert can_edit_entry(registered_user, entry) is False


def test_admin_can_edit_public_of_other_user(admin_user, other_user):
    """Positive: admin boleh ubah/hapus data public milik siapa pun."""
    entry = build_entry(other_user, VISIBILITY_PUBLIC)
    assert can_edit_entry(admin_user, entry) is True


def test_admin_cannot_see_private_of_other_user(admin_user, other_user):
    """Negative (security): admin pun ga bisa liat private orang lain."""
    entry = build_entry(other_user, VISIBILITY_PRIVATE)
    assert can_view_entry(admin_user, entry) is False
    assert can_edit_entry(admin_user, entry) is False