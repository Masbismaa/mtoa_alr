"""Test aturan hak akses data link (SR-04)."""
from app.models import AccessEntry, AuditLog
from app.security.access_policy import can_edit_entry, can_view_audit_data ,can_view_entry
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

def build_entry_audit_log(actor, old_visibility, new_visibility):
    """Helper: audit log perubahan data link."""
    return AuditLog(
        user_id=actor.id, action="update", entity_type="access_entries",
        old_data={"title": "VPN", "visibility": old_visibility},
        new_data={"title": "VPN", "visibility": new_visibility},
    )

def test_admin_can_view_public_audit_data(admin_user, other_user):
    """Positive: admin bisa liat isi perubahan data Public orang lain."""
    audit_log = build_entry_audit_log(other_user, VISIBILITY_PUBLIC, VISIBILITY_PUBLIC)
    assert can_view_audit_data(admin_user, audit_log) is True

def test_admin_cannot_view_private_audit_data_of_other_user(admin_user, other_user):
    """Negative (security): data yg pernah Private punya orang lain tetep ketutup buat admin."""
    audit_log = build_entry_audit_log(other_user, VISIBILITY_PUBLIC, VISIBILITY_PRIVATE)
    assert can_view_audit_data(admin_user, audit_log) is False

def test_admin_can_view_own_private_audit_data(admin_user):
    """Positive: data Private punya admin sendiri boleh diliat."""
    audit_log = build_entry_audit_log(admin_user, VISIBILITY_PRIVATE, VISIBILITY_PRIVATE)
    assert can_view_audit_data(admin_user, audit_log) is True

def test_user_entry_cannot_view_audit_data(registered_user):
    """Negative (RBAC): user biasa ga bisa liat isi audit log, walaupun punya sendiri."""
    audit_log = build_entry_audit_log(registered_user, VISIBILITY_PUBLIC, VISIBILITY_PUBLIC)
    assert can_view_audit_data(registered_user, audit_log) is False