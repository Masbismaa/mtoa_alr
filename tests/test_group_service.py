"""Test logika group: bikin, undang, share link, keluar."""
import pytest
from app.extensions import db
from app.models import AccessEntry, GroupEntry, GroupMember
from app.security.access_policy import can_edit_entry
from app.services.access_entry_service import create_access_entry, get_visible_entry, search_visible_entries
from app.services.group_service import (
    accept_invitation,
    add_group_entry,
    create_group,
    decline_invitation,
    delete_group,
    get_member_group,
    invite_member,
    leave_group,
    remove_member,
    update_group,
)
from app.utils.constants import GROUP_MEMBER_STATUS_ACTIVE, GROUP_MEMBER_STATUS_INVITED, GROUP_ROLE_OWNER, VISIBILITY_PRIVATE
from app.utils.exceptions import PermissionDeniedError, ValidationError


def create_entry(user, category, title, url):
    """Helper: bikin link private."""
    return create_access_entry(user, {
        "category_id": category.id, "title": title, "url": url,
        "address": "", "port": "", "username": "", "access_note": "", "description": "",
        "visibility": VISIBILITY_PRIVATE,
    })


def create_group_with_member(owner, member_user):
    """Helper: group + 1 anggota yg udah nerima undangan."""
    group = create_group(owner, {"name": "Tim Network"})
    invitation = invite_member(owner, group, member_user.email)
    accept_invitation(member_user, invitation)
    return group


def test_create_group_makes_owner_member(app, registered_user):
    """Positive: pembuat langsung jadi pemilik & anggota aktif."""
    group = create_group(registered_user, {"name": "Tim Network", "description": "Link perangkat jaringan"})
    assert group.user_id == registered_user.id
    assert group.member_list[0].role == GROUP_ROLE_OWNER
    assert group.member_list[0].status == GROUP_MEMBER_STATUS_ACTIVE


def test_create_group_requires_name(app, registered_user):
    """Negative: nama group wajib."""
    with pytest.raises(ValidationError):
        create_group(registered_user, {"name": "  "})


def test_update_group_by_non_owner_denied(app, registered_user, other_user):
    """Negative (security): anggota biasa ga bisa ngubah group."""
    group = create_group_with_member(registered_user, other_user)
    with pytest.raises(PermissionDeniedError):
        update_group(other_user, group, {"name": "Diubah"})


def test_invite_member_status_invited(app, registered_user, other_user):
    """Positive: yg diundang statusnya invited & belum bisa buka group."""
    group = create_group(registered_user, {"name": "Tim Network"})
    member = invite_member(registered_user, group, "  USER.LAIN@spindo.com ")
    assert member.status == GROUP_MEMBER_STATUS_INVITED
    assert get_member_group(other_user, group.id) is None


def test_invite_unknown_email_rejected(app, registered_user):
    """Negative: email yg belum daftar ditolak."""
    group = create_group(registered_user, {"name": "Tim Network"})
    with pytest.raises(ValidationError):
        invite_member(registered_user, group, "ga.ada@spindo.com")


def test_invite_duplicate_rejected(app, registered_user, other_user):
    """Negative: ga bisa ngundang orang yg sama 2x (atau diri sendiri)."""
    group = create_group(registered_user, {"name": "Tim Network"})
    invite_member(registered_user, group, other_user.email)
    with pytest.raises(ValidationError):
        invite_member(registered_user, group, other_user.email)
    with pytest.raises(ValidationError):
        invite_member(registered_user, group, registered_user.email)


def test_non_owner_cannot_invite(app, registered_user, other_user, admin_user):
    """Negative (security): anggota biasa ga bisa ngundang."""
    group = create_group_with_member(registered_user, other_user)
    with pytest.raises(PermissionDeniedError):
        invite_member(other_user, group, admin_user.email)


def test_accept_invitation_gives_access(app, registered_user, other_user):
    """Positive: abis nerima undangan, group bisa dibuka."""
    group = create_group_with_member(registered_user, other_user)
    assert get_member_group(other_user, group.id) is not None


def test_decline_invitation_removes_membership(app, registered_user, other_user):
    """Positive: nolak undangan -> datanya ilang."""
    group = create_group(registered_user, {"name": "Tim Network"})
    invitation = invite_member(registered_user, group, other_user.email)
    decline_invitation(other_user, invitation)
    assert db.session.execute(
        db.select(db.func.count(GroupMember.id)).filter_by(user_id=other_user.id)
    ).scalar() == 0


def test_shared_private_entry_visible_to_active_member(app, registered_user, other_user, category_dict):
    """Positive: link private yg dibagi ke group keliatan sama anggota, tapi read-only."""
    group = create_group_with_member(registered_user, other_user)
    entry = create_entry(registered_user, category_dict["Web"], "Portal VPN", "https://vpn.spindo.com")
    add_group_entry(registered_user, group, entry.id)
    assert get_visible_entry(other_user, entry.id) is not None
    assert search_visible_entries(other_user, keyword="vpn").total == 1
    assert can_edit_entry(other_user, entry) is False


def test_invited_member_cannot_see_shared_entry(app, registered_user, other_user, category_dict):
    """Negative (security): yg masih diundang belum boleh liat link group."""
    group = create_group(registered_user, {"name": "Tim Network"})
    invite_member(registered_user, group, other_user.email)
    entry = create_entry(registered_user, category_dict["Web"], "Portal VPN", "https://vpn.spindo.com")
    add_group_entry(registered_user, group, entry.id)
    assert get_visible_entry(other_user, entry.id) is None


def test_cannot_reshare_private_entry_from_other_group(app, registered_user, other_user, category_dict):
    """Negative (security): link private orang lain ga bisa di-share ulang ke group lain."""
    first_group = create_group_with_member(registered_user, other_user)
    entry = create_entry(registered_user, category_dict["Web"], "Portal VPN", "https://vpn.spindo.com")
    add_group_entry(registered_user, first_group, entry.id)
    second_group = create_group(other_user, {"name": "Group Lain"})
    with pytest.raises(ValidationError):
        add_group_entry(other_user, second_group, entry.id)


def test_member_leave_removes_their_shared_entry(app, registered_user, other_user, category_dict):
    """Positive (security): anggota keluar -> link yg dia bagi ikut dicabut."""
    group = create_group_with_member(registered_user, other_user)
    entry = create_entry(other_user, category_dict["Web"], "Punya Lain", "https://lain.spindo.com")
    add_group_entry(other_user, group, entry.id)
    leave_group(other_user, group)
    assert group.group_entry_list == []
    assert get_visible_entry(registered_user, entry.id) is None


def test_owner_cannot_leave(app, registered_user):
    """Negative: pemilik ga bisa keluar dari group sendiri."""
    group = create_group(registered_user, {"name": "Tim Network"})
    with pytest.raises(ValidationError):
        leave_group(registered_user, group)


def test_remove_member_by_owner(app, registered_user, other_user):
    """Positive: pemilik bisa ngeluarin anggota."""
    group = create_group_with_member(registered_user, other_user)
    member = next(item for item in group.member_list if item.user_id == other_user.id)
    remove_member(registered_user, group, member.id)
    assert get_member_group(other_user, group.id) is None


def test_delete_group_keeps_access_entries(app, registered_user, category_dict):
    """Positive: hapus group, data link aslinya tetep ada."""
    group = create_group(registered_user, {"name": "Tim Network"})
    entry = create_entry(registered_user, category_dict["Web"], "Portal HR", "https://hr.spindo.com")
    add_group_entry(registered_user, group, entry.id)
    delete_group(registered_user, group)
    assert db.session.execute(db.select(db.func.count(GroupEntry.id))).scalar() == 0
    assert db.session.execute(db.select(db.func.count(AccessEntry.id))).scalar() == 1