"""Aturan hak akses data link & group. Satu tempat, dipake route, service, dan query."""
from sqlalchemy import or_
from app.extensions import db
from app.models import AccessEntry, Group, GroupEntry, GroupEntryViewer, GroupMember
from app.utils.constants import (
    GROUP_MEMBER_STATUS_ACTIVE,
    PERMISSION_EDIT_PUBLIC_ENTRIES,
    PERMISSION_VIEW_AUDIT_LOGS,
    ROLE_ADMIN,
    VISIBILITY_PRIVATE,
    VISIBILITY_PUBLIC,
)

def is_entry_owner(user, entry):
    """True kalau user yg bikin data ini."""
    return entry.user_id == user.id

def build_shared_entry_id_query(user):
    """Query id link yg dibagiin ke user lewat group: anggota aktif, dan link-nya ga dibatasi atau user boleh liat."""
    is_viewer_condition = (
        db.select(GroupEntryViewer.id)
        .where(GroupEntryViewer.group_entry_id == GroupEntry.id, GroupEntryViewer.user_id == user.id)
        .exists()
    )
    return (
        db.select(GroupEntry.access_entry_id)
        .join(GroupMember, GroupMember.group_id == GroupEntry.group_id)
        .join(Group, Group.id == GroupEntry.group_id)
        .where(
            GroupMember.user_id == user.id,
            GroupMember.status == GROUP_MEMBER_STATUS_ACTIVE,
            or_(
                GroupEntry.is_restricted.is_(False),
                Group.user_id == user.id,
                GroupEntry.user_id == user.id,
                is_viewer_condition,
            ),
        )
    )

def is_entry_shared_with_user(user, entry):
    """True kalau link ini ada di group yg user jadi anggota aktifnya."""
    if entry.id is None:
        return False
    shared_query = build_shared_entry_id_query(user).where(GroupEntry.access_entry_id == entry.id).limit(1)
    return db.session.execute(shared_query).first() is not None

def can_view_entry(user, entry):
    """Boleh liat: punya sendiri, Public, atau dibagiin lewat group."""
    if is_entry_owner(user, entry) or entry.visibility == VISIBILITY_PUBLIC:
        return True
    return is_entry_shared_with_user(user, entry)

def can_edit_entry(user, entry):
    """Boleh ubah/hapus: punya sendiri, atau yg punya akses edit link Public. Anggota group cuma bisa liat."""
    if is_entry_owner(user, entry):
        return True
    return entry.visibility == VISIBILITY_PUBLIC and has_permission(user, PERMISSION_EDIT_PUBLIC_ENTRIES)

def build_visible_entry_filter(user):
    """Filter query: data yg boleh dilihat user (sama kayak can_view_entry)."""
    return or_(
        AccessEntry.user_id == user.id,
        AccessEntry.visibility == VISIBILITY_PUBLIC,
        AccessEntry.id.in_(build_shared_entry_id_query(user)),
    )

def build_shareable_entry_filter(user):
    """Filter data yg boleh dibagiin ke group: punya sendiri / Public (hasil share group lain ga boleh)."""
    return or_(AccessEntry.user_id == user.id, AccessEntry.visibility == VISIBILITY_PUBLIC)

def get_group_membership(user, group):
    """Data keanggotaan user di group ini, None kalau bukan anggota."""
    return next((member for member in group.member_list if member.user_id == user.id), None)

def is_group_owner(user, group):
    """True kalau user pemilik group."""
    return group.user_id == user.id

def can_add_group_entry(user, group):
    """Boleh nambah link ke group: pemilik, atau anggota aktif yg dikasih izin pemilik."""
    if is_group_owner(user, group):
        return True
    membership = get_group_membership(user, group)
    return membership is not None and membership.status == GROUP_MEMBER_STATUS_ACTIVE and membership.can_add_entry

def can_view_group_entry(user, group, group_entry):
    """Boleh liat link di group (sama kayak build_shared_entry_id_query, plus pemilik link-nya sendiri)."""
    if not group_entry.is_restricted or is_group_owner(user, group) or group_entry.user_id == user.id:
        return True
    return group_entry.access_entry.user_id == user.id or any(viewer.user_id == user.id for viewer in group_entry.viewer_list)

def is_admin(user):
    """True kalau user ber-role admin."""
    return user.role == ROLE_ADMIN

def has_permission(user, permission_key):
    """Admin otomatis punya semua akses, user biasa cuma yg di-grant admin."""
    if is_admin(user):
        return True
    return any(permission.permission_key == permission_key for permission in user.permission_list)

def is_private_audit_data(audit_log):
    """True kalau isi audit log ini data Private (sebelum atau sesudah berubah)."""
    return any(
        (data_dict or {}).get("visibility") == VISIBILITY_PRIVATE
        for data_dict in (audit_log.old_data, audit_log.new_data)
    )

def can_view_audit_data(user, audit_log):
    """Yg punya akses audit log boleh liat isi perubahan, kecuali data Private punya orang lain."""
    if not has_permission(user, PERMISSION_VIEW_AUDIT_LOGS):
        return False
    return audit_log.user_id == user.id or not is_private_audit_data(audit_log)