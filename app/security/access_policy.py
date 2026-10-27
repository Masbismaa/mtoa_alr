"""Aturan hak akses data link & group. Satu tempat, dipake route, service, dan query."""
from sqlalchemy import or_, true
from sqlalchemy.orm import aliased
from app.extensions import db
from app.models import AccessEntry, Group, GroupEntry, GroupEntryViewer, GroupMember
from app.utils.constants import (
    GROUP_MEMBER_STATUS_ACTIVE,
    ROLE_ADMIN,
    VISIBILITY_PRIVATE,
    VISIBILITY_PUBLIC,
)

def is_entry_owner(user, entry):
    """True kalau user yg bikin data ini."""
    return entry.user_id == user.id

def build_visible_group_entry_condition(user):
    """SATU-SATUNYA aturan link di group yg boleh diliat user: link ga terbatas, atau user = pemilik group /
    yg nambahin link / pemilik link-nya / viewer yg dipilih. Dipake daftar & hitungan di halaman group
    (group_service) dan akses detail link (build_shared_entry_id_query), jadi hasilnya selalu sama.
    Query pemakainya wajib join Group. Pemilik link dicek pake alias biar ga nyambung ke AccessEntry di query luar."""
    link_entry = aliased(AccessEntry)
    is_viewer = db.select(GroupEntryViewer.id).where(
        GroupEntryViewer.group_entry_id == GroupEntry.id, GroupEntryViewer.user_id == user.id,
    ).exists()
    is_link_owner = db.select(link_entry.id).where(
        link_entry.id == GroupEntry.access_entry_id, link_entry.user_id == user.id,
    ).exists()
    return or_(GroupEntry.is_restricted.is_(False), Group.user_id == user.id, GroupEntry.user_id == user.id,
               is_link_owner, is_viewer)

def build_shared_entry_id_query(user):
    """Query id link yg dibagiin ke user lewat group: anggota aktif + boleh liat link-nya (aturan di atas)."""
    return (
        db.select(GroupEntry.access_entry_id)
        .join(GroupMember, GroupMember.group_id == GroupEntry.group_id)
        .join(Group, Group.id == GroupEntry.group_id)
        .where(
            GroupMember.user_id == user.id,
            GroupMember.status == GROUP_MEMBER_STATUS_ACTIVE,
            build_visible_group_entry_condition(user),
        )
    )

def is_entry_shared_with_user(user, entry):
    """True kalau link ini ada di group yg user jadi anggota aktifnya."""
    if entry.id is None:
        return False
    shared_query = build_shared_entry_id_query(user).where(GroupEntry.access_entry_id == entry.id).limit(1)
    return db.session.execute(shared_query).first() is not None

def can_view_entry(user, entry):
    """Boleh liat: punya sendiri, Public, dibagiin lewat group, atau admin (semua link, Private orang lain
    cuma read-only karena can_edit_entry tetep nolak)."""
    if is_admin(user) or is_entry_owner(user, entry) or entry.visibility == VISIBILITY_PUBLIC:
        return True
    return is_entry_shared_with_user(user, entry)

def can_edit_entry(user, entry):
    """Boleh ubah/hapus: punya sendiri, atau admin buat link Public. Anggota group cuma bisa liat."""
    if is_entry_owner(user, entry):
        return True
    return entry.visibility == VISIBILITY_PUBLIC and is_admin(user)

def build_visible_entry_filter(user):
    """Filter query: data yg boleh dilihat user (sama kayak can_view_entry). Admin liat semua."""
    if is_admin(user):
        return true()
    return build_own_visible_entry_filter(user)

def build_own_visible_entry_filter(user):
    """Data sendiri + Public + dibagiin lewat group, tanpa hak liat admin. Dipake cek link duplikat,
    biar admin ga keblok gara-gara URL yg sama ada di link Private orang lain."""
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

def is_admin(user):
    """True kalau user ber-role admin."""
    return user.role == ROLE_ADMIN

def is_private_audit_data(audit_log):
    """True kalau isi audit log ini data Private (sebelum atau sesudah berubah)."""
    return any(
        (data_dict or {}).get("visibility") == VISIBILITY_PRIVATE
        for data_dict in (audit_log.old_data, audit_log.new_data)
    )
