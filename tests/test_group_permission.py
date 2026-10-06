"""Test izin anggota group: default cuma liat, izin tambah link per anggota, link terbatas per anggota."""
import pytest
from app.extensions import db
from app.models import AuditLog, GroupEntry, GroupEntryViewer
from app.services import auth_service
from app.services.access_entry_service import create_access_entry, get_visible_entry
from app.services.group_service import (
    accept_invitation,
    add_group_entry,
    create_group,
    invite_member,
    leave_group,
    list_visible_group_entry,
    set_group_entry_viewers,
    set_member_can_add_entry,
)
from app.utils.constants import VISIBILITY_PRIVATE, VISIBILITY_PUBLIC
from app.utils.exceptions import PermissionDeniedError, ValidationError

PASSWORD = "PasswordKuat123"

@pytest.fixture()
def third_user(app):
    """User ketiga buat ngetes link terbatas."""
    return auth_service.register_user(
        email="user.ketiga@spindo.com", password=PASSWORD, full_name="User Ketiga", department="HR", job_title="Staff",
    )

def create_entry(user, category, title, visibility=VISIBILITY_PRIVATE):
    """Helper: bikin link (default private)."""
    return create_access_entry(user, {
        "category_id": category.id, "title": title, "url": f"https://{title.lower().replace(' ', '-')}.spindo.com",
        "address": "", "port": "", "username": "", "access_note": "", "description": "",
        "visibility": visibility,
    })

def join_group(owner, group, member_user):
    """Helper: undang + terima. Return data keanggotaan."""
    invitation = invite_member(owner, group, member_user.email)
    accept_invitation(member_user, invitation)
    return invitation

def test_new_member_is_read_only(app, registered_user, other_user, category_dict):
    """Negative: anggota baru defaultnya cuma bisa liat, nambah link ditolak."""
    group = create_group(registered_user, {"name": "Tim Network"})
    member = join_group(registered_user, group, other_user)
    entry = create_entry(other_user, category_dict["Web"], "Punya Anggota")
    assert member.can_add_entry is False
    with pytest.raises(PermissionDeniedError):
        add_group_entry(other_user, group, entry.id)
    assert group.group_entry_list == []

def test_owner_grants_and_revokes_add_permission(app, registered_user, other_user, category_dict):
    """Positive: pemilik kasih izin -> anggota bisa nambah, dicabut -> ditolak lagi. Dua-duanya kecatat di audit log."""
    group = create_group(registered_user, {"name": "Tim Network"})
    member = join_group(registered_user, group, other_user)
    set_member_can_add_entry(registered_user, group, member.id, True)
    add_group_entry(other_user, group, create_entry(other_user, category_dict["Web"], "Link Satu").id)
    set_member_can_add_entry(registered_user, group, member.id, False)
    with pytest.raises(PermissionDeniedError):
        add_group_entry(other_user, group, create_entry(other_user, category_dict["Web"], "Link Dua").id)
    audit_list = db.session.execute(
        db.select(AuditLog).where(AuditLog.entity_type == "group_members", AuditLog.entity_id == str(member.id))
        .order_by(AuditLog.id)
    ).scalars().all()
    assert [audit.new_data.get("can_add_entry") for audit in audit_list][-2:] == [True, False]

def test_member_cannot_change_permission(app, registered_user, other_user, third_user):
    """Negative (security): anggota biasa ga bisa ngubah izin siapa pun."""
    group = create_group(registered_user, {"name": "Tim Network"})
    join_group(registered_user, group, other_user)
    third_member = join_group(registered_user, group, third_user)
    with pytest.raises(PermissionDeniedError):
        set_member_can_add_entry(other_user, group, third_member.id, True)
    assert third_member.can_add_entry is False

def test_owner_permission_cannot_be_changed(app, registered_user):
    """Negative: izin pemilik ga bisa diubah (pemilik selalu boleh)."""
    group = create_group(registered_user, {"name": "Tim Network"})
    with pytest.raises(ValidationError):
        set_member_can_add_entry(registered_user, group, group.member_list[0].id, False)

def test_restricted_entry_only_for_picked_member(app, registered_user, other_user, third_user, category_dict):
    """Positive + security: link terbatas cuma keliatan buat anggota yg dicentang."""
    group = create_group(registered_user, {"name": "Tim Network"})
    join_group(registered_user, group, other_user)
    join_group(registered_user, group, third_user)
    entry = create_entry(registered_user, category_dict["Web"], "Router Inti")
    group_entry = add_group_entry(registered_user, group, entry.id)
    set_group_entry_viewers(registered_user, group, group_entry.id, True, [str(other_user.id)])
    assert get_visible_entry(other_user, entry.id) is not None
    assert get_visible_entry(third_user, entry.id) is None

def test_unrestrict_clears_viewers(app, registered_user, other_user, third_user, category_dict):
    """Positive: balik ke "Semua anggota" -> daftar viewer dikosongin, semua anggota bisa liat lagi."""
    group = create_group(registered_user, {"name": "Tim Network"})
    join_group(registered_user, group, other_user)
    join_group(registered_user, group, third_user)
    entry = create_entry(registered_user, category_dict["Web"], "Router Inti")
    group_entry = add_group_entry(registered_user, group, entry.id)
    set_group_entry_viewers(registered_user, group, group_entry.id, True, [str(other_user.id)])
    set_group_entry_viewers(registered_user, group, group_entry.id, False, [str(other_user.id)])
    assert group_entry.viewer_list == []
    assert get_visible_entry(third_user, entry.id) is not None

def test_adder_still_sees_restricted_entry(app, registered_user, other_user, third_user, category_dict):
    """Positive: anggota yg nambahin link tetep liat link itu di group walaupun ga dicentang."""
    group = create_group(registered_user, {"name": "Tim Network"})
    member = join_group(registered_user, group, other_user)
    join_group(registered_user, group, third_user)
    set_member_can_add_entry(registered_user, group, member.id, True)
    entry = create_entry(registered_user, category_dict["Web"], "Portal Umum", visibility=VISIBILITY_PUBLIC)
    group_entry = add_group_entry(other_user, group, entry.id)
    set_group_entry_viewers(registered_user, group, group_entry.id, True, [str(third_user.id)])
    assert group_entry in list_visible_group_entry(other_user, group)

@pytest.mark.parametrize("bad_id", ["999", "abc"])
def test_unknown_viewer_rejected(app, registered_user, other_user, category_dict, bad_id):
    """Negative (security): id user di luar anggota group ditolak."""
    group = create_group(registered_user, {"name": "Tim Network"})
    join_group(registered_user, group, other_user)
    group_entry = add_group_entry(registered_user, group, create_entry(registered_user, category_dict["Web"], "Router").id)
    with pytest.raises(ValidationError):
        set_group_entry_viewers(registered_user, group, group_entry.id, True, [bad_id])
    assert group_entry.is_restricted is False

def test_member_cannot_set_viewers(app, registered_user, other_user, category_dict):
    """Negative (security): anggota biasa ga bisa ngatur siapa yg bisa liat."""
    group = create_group(registered_user, {"name": "Tim Network"})
    join_group(registered_user, group, other_user)
    group_entry = add_group_entry(registered_user, group, create_entry(registered_user, category_dict["Web"], "Router").id)
    with pytest.raises(PermissionDeniedError):
        set_group_entry_viewers(other_user, group, group_entry.id, True, [])

def test_leave_removes_viewer_row(app, registered_user, other_user, category_dict):
    """Positive: anggota keluar -> izin liat link terbatasnya ikut kehapus."""
    group = create_group(registered_user, {"name": "Tim Network"})
    join_group(registered_user, group, other_user)
    group_entry = add_group_entry(registered_user, group, create_entry(registered_user, category_dict["Web"], "Router").id)
    set_group_entry_viewers(registered_user, group, group_entry.id, True, [str(other_user.id)])
    leave_group(other_user, group)
    assert db.session.execute(db.select(GroupEntryViewer)).scalars().all() == []

def test_read_only_member_page(logged_in_client, registered_user, other_user):
    """Positive: anggota read-only ga liat tombol Link Baru & form tambah, kirim langsung -> 403."""
    group = create_group(other_user, {"name": "Group Orang"})
    join_group(other_user, group, registered_user)
    html_text = logged_in_client.get(f"/groups/{group.id}").get_data(as_text=True)
    assert "Link Baru" not in html_text
    assert "hanya bisa melihat" in html_text
    assert logged_in_client.post(f"/groups/{group.id}/entries", data={"entry_id": "1"}).status_code == 403

def test_read_only_member_new_entry_not_added_to_group(logged_in_client, registered_user, other_user, category_dict):
    """Negative (security): anggota read-only bikin link lewat ?group_id -> link kesimpen, tapi ga masuk group."""
    group = create_group(other_user, {"name": "Group Orang"})
    join_group(other_user, group, registered_user)
    response = logged_in_client.post("/entries/new", data={
        "category_id": str(category_dict["Web"].id), "title": "Coba Masuk", "url": "https://coba.spindo.com",
        "visibility": VISIBILITY_PRIVATE, "group_id": str(group.id),
    })
    assert response.status_code == 302
    assert f"/groups/{group.id}" not in response.location
    assert db.session.execute(db.select(db.func.count(GroupEntry.id))).scalar() == 0

def test_hidden_entry_not_listed_on_group_page(logged_in_client, registered_user, other_user, third_user, category_dict):
    """Negative (security): link terbatas ga muncul di halaman group buat anggota yg ga dicentang."""
    group = create_group(other_user, {"name": "Group Orang"})
    join_group(other_user, group, registered_user)
    join_group(other_user, group, third_user)
    group_entry = add_group_entry(other_user, group, create_entry(other_user, category_dict["Web"], "Server Rahasia").id)
    set_group_entry_viewers(other_user, group, group_entry.id, True, [str(third_user.id)])
    assert "Server Rahasia" not in logged_in_client.get(f"/groups/{group.id}").get_data(as_text=True)

def test_owner_toggles_permission_via_route(logged_in_client, registered_user, other_user):
    """Positive: pemilik klik tombol izin -> anggota boleh nambah link."""
    group = create_group(registered_user, {"name": "Tim Network"})
    member = join_group(registered_user, group, other_user)
    response = logged_in_client.post(f"/groups/{group.id}/members/{member.id}/permission", data={"can_add_entry": "1"})
    assert response.status_code == 302
    assert member.can_add_entry is True

def test_member_cannot_open_viewer_page(logged_in_client, registered_user, other_user, category_dict):
    """Negative (security): anggota biasa 403 di halaman atur akses link & tombol izin."""
    group = create_group(other_user, {"name": "Group Orang"})
    member = join_group(other_user, group, registered_user)
    group_entry = add_group_entry(other_user, group, create_entry(other_user, category_dict["Web"], "Router").id)
    assert logged_in_client.get(f"/groups/{group.id}/entries/{group_entry.id}/viewers").status_code == 403
    assert logged_in_client.post(f"/groups/{group.id}/members/{member.id}/permission", data={"can_add_entry": "1"}).status_code == 403
    assert member.can_add_entry is False

def test_owner_saves_viewers_via_route(logged_in_client, registered_user, other_user, category_dict):
    """Positive: pemilik simpan pengaturan akses link lewat halaman."""
    group = create_group(registered_user, {"name": "Tim Network"})
    join_group(registered_user, group, other_user)
    group_entry = add_group_entry(registered_user, group, create_entry(registered_user, category_dict["Web"], "Router").id)
    url = f"/groups/{group.id}/entries/{group_entry.id}/viewers"
    assert "Anggota tertentu" in logged_in_client.get(url).get_data(as_text=True)
    response = logged_in_client.post(url, data={"is_restricted": "1", "viewer_user_id": [str(other_user.id)]})
    assert response.status_code == 302
    assert group_entry.is_restricted is True
    assert [viewer.user_id for viewer in group_entry.viewer_list] == [other_user.id]

def test_unknown_group_entry_viewer_page_404(logged_in_client, registered_user):
    """Negative: id link ngasal -> 404."""
    group = create_group(registered_user, {"name": "Tim Network"})
    assert logged_in_client.get(f"/groups/{group.id}/entries/999/viewers").status_code == 404
