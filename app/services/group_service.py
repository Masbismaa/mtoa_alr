"""Logika group: bikin, undang anggota, izin tambah link, bagi link (bisa dibatasi per anggota), keluar/dikeluarin."""
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import or_
from app.extensions import db
from app.models import AccessEntry, Group, GroupEntry, GroupEntryViewer, GroupMember, User
from app.security.access_policy import (
    build_shareable_entry_filter,
    build_visible_group_entry_condition,
    can_add_group_entry,
    get_group_membership,
    is_group_owner,
)
from app.services.audit_service import log_audit
from app.services.user_notification_service import GROUP_LIST_PATH, add_notification, build_group_path
from app.utils.constants import (
    AUDIT_ACTION_CREATE,
    AUDIT_ACTION_DELETE,
    AUDIT_ACTION_UPDATE,
    GROUP_ENTRY_OPTION_LIMIT,
    GROUP_MEMBER_STATUS_ACTIVE,
    GROUP_MEMBER_STATUS_INVITED,
    GROUP_ROLE_MEMBER,
    GROUP_ROLE_OWNER,
    MAX_GROUP_DESCRIPTION_LENGTH,
    MAX_GROUP_NAME_LENGTH,
    PER_PAGE,
)
from app.utils.exceptions import PermissionDeniedError, ValidationError, build_error
from app.utils.query_helper import build_keyword_filter, parse_positive_int
from app.utils.selection import apply_condition_list, build_text_selection_filter
from app.utils.sanitizer import sanitize_text
from app.utils.text_helper import normalize_email

AUDIT_GROUP = "groups"
AUDIT_GROUP_MEMBER = "group_members"
AUDIT_GROUP_ENTRY = "group_entries"

def validate_group_data(data_dict):
    """Cek nama & deskripsi group, balikin data yg udah bersih."""
    clean_name = sanitize_text(data_dict.get("name"), max_length=MAX_GROUP_NAME_LENGTH)
    if not clean_name:
        raise ValidationError([build_error("name", "Group name is required")])
    clean_description = sanitize_text(data_dict.get("description"), max_length=MAX_GROUP_DESCRIPTION_LENGTH) or None
    return {"name": clean_name, "description": clean_description}

def build_group_audit_dict(group):
    """Data group buat audit log."""
    return {"name": group.name, "description": group.description}

def create_group(user, data_dict):
    """Bikin group baru, pembuatnya langsung jadi pemilik."""
    clean_dict = validate_group_data(data_dict)
    group = Group(user_id=user.id, **clean_dict)
    group.member_list.append(GroupMember(user_id=user.id, role=GROUP_ROLE_OWNER, status=GROUP_MEMBER_STATUS_ACTIVE))
    db.session.add(group)
    db.session.flush()
    log_audit(AUDIT_ACTION_CREATE, AUDIT_GROUP, entity_id=group.id, new_data_dict=build_group_audit_dict(group), user=user)
    db.session.commit()
    return group

def update_group(user, group, data_dict):
    """Ubah nama/deskripsi, cuma pemilik."""
    ensure_group_owner(user, group, "Only the group owner can change the group")
    clean_dict = validate_group_data(data_dict)
    old_data_dict = build_group_audit_dict(group)
    group.name = clean_dict["name"]
    group.description = clean_dict["description"]
    log_audit(
        AUDIT_ACTION_UPDATE, AUDIT_GROUP, entity_id=group.id,
        old_data_dict=old_data_dict, new_data_dict=build_group_audit_dict(group), user=user,
    )
    db.session.commit()
    return group

def delete_group(user, group):
    """Hapus group beserta anggota & daftar link-nya. Data link aslinya tetep aman."""
    ensure_group_owner(user, group, "Only the group owner can delete the group")
    log_audit(AUDIT_ACTION_DELETE, AUDIT_GROUP, entity_id=group.id, old_data_dict=build_group_audit_dict(group), user=user)
    db.session.delete(group)
    db.session.commit()

def get_member_group(user, group_id):
    """Group yg user jadi anggota aktifnya. None kalau bukan anggota (jadi 404).
    Anggota (+ data user-nya) ikut diambil karena dipake cek peran di tiap aksi & jumlahnya kecil.
    Link group SENGAJA ga diambil di sini (bisa ribuan): halaman detail ngambilnya sendiri per halaman
    lewat search_visible_group_entry."""
    return db.session.execute(
        db.select(Group)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .options(
            joinedload(Group.owner),
            selectinload(Group.member_list).joinedload(GroupMember.user),
        )
        .where(
            Group.id == group_id,
            GroupMember.user_id == user.id,
            GroupMember.status == GROUP_MEMBER_STATUS_ACTIVE,
        )
    ).scalar_one_or_none()

def build_group_role_condition(user, role_list):
    """Filter peran user di group: cuma Pemilik atau cuma Anggota. Dua-duanya / kosong = ga difilter."""
    if role_list == [GROUP_ROLE_OWNER]:
        return Group.user_id == user.id
    if role_list == [GROUP_ROLE_MEMBER]:
        return Group.user_id != user.id
    return None

def list_user_group(user, selection=None):
    """Semua group yg user jadi anggota aktifnya. selection = kriteria Select Screen halaman Groups."""
    query = (
        db.select(Group)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .where(GroupMember.user_id == user.id, GroupMember.status == GROUP_MEMBER_STATUS_ACTIVE)
    )
    if selection:
        query = apply_condition_list(query, [
            build_keyword_filter([Group.name, Group.description], selection["keyword"]) if selection["keyword"] else None,
            build_text_selection_filter([Group.name], selection["name"]),
            build_group_role_condition(user, selection["role_list"]),
        ])
    return db.session.execute(query.order_by(Group.name)).scalars().all()

def count_visible_group_entries(user, group_list):
    """Hitung link semua group dalam satu query dengan aturan visibilitas yang sama."""
    group_ids = [group.id for group in group_list]
    if not group_ids:
        return {}
    active_membership = db.select(GroupMember.id).where(
        GroupMember.group_id == Group.id, GroupMember.user_id == user.id,
        GroupMember.status == GROUP_MEMBER_STATUS_ACTIVE,
    ).exists()
    counts = dict(db.session.execute(
        db.select(GroupEntry.group_id, db.func.count(GroupEntry.id))
        .join(Group, Group.id == GroupEntry.group_id).join(AccessEntry, AccessEntry.id == GroupEntry.access_entry_id)
        .where(Group.id.in_(group_ids), active_membership, build_visible_group_entry_condition(user))
        .group_by(GroupEntry.group_id)
    ).all())
    return {group_id: counts.get(group_id, 0) for group_id in group_ids}

def search_visible_group_entry(user, group, page=1, per_page=PER_PAGE):
    """Link di group yg boleh diliat user, per halaman, disaring di SQL (bukan ngambil semua terus disaring di Python).
    Halaman kebablasan (misal link-nya abis dicabut) dijepit ke halaman terakhir."""
    query = (
        db.select(GroupEntry)
        .join(Group, Group.id == GroupEntry.group_id)
        .join(AccessEntry, AccessEntry.id == GroupEntry.access_entry_id)
        .options(
            joinedload(GroupEntry.added_by),
            selectinload(GroupEntry.viewer_list),
            joinedload(GroupEntry.access_entry).options(joinedload(AccessEntry.category), joinedload(AccessEntry.owner)),
        )
        .where(GroupEntry.group_id == group.id, build_visible_group_entry_condition(user))
        .order_by(GroupEntry.id)
    )
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    if pagination.pages and page > pagination.pages:
        pagination = db.paginate(query, page=pagination.pages, per_page=per_page, error_out=False)
    return pagination

def count_active_member(group_list):
    """{group_id: jumlah anggota aktif} dalam satu query, ga perlu ngambil semua baris anggota."""
    group_ids = [group.id for group in group_list]
    if not group_ids:
        return {}
    counts = dict(db.session.execute(
        db.select(GroupMember.group_id, db.func.count(GroupMember.id))
        .where(GroupMember.group_id.in_(group_ids), GroupMember.status == GROUP_MEMBER_STATUS_ACTIVE)
        .group_by(GroupMember.group_id)
    ).all())
    return {group_id: counts.get(group_id, 0) for group_id in group_ids}

def count_pending_invitation(user):
    """Jumlah undangan yg belum dijawab user."""
    return db.session.scalar(
        db.select(db.func.count(GroupMember.id))
        .where(GroupMember.user_id == user.id, GroupMember.status == GROUP_MEMBER_STATUS_INVITED)
    )

def list_pending_invitation(user):
    """Undangan yg belum dijawab user."""
    return db.session.execute(
        db.select(GroupMember)
        .options(joinedload(GroupMember.group).joinedload(Group.owner))
        .where(GroupMember.user_id == user.id, GroupMember.status == GROUP_MEMBER_STATUS_INVITED)
        .order_by(GroupMember.id.desc())
    ).scalars().all()

def get_own_invitation(user, member_id):
    """Undangan punya user sendiri yg masih nunggu. None kalau bukan."""
    return db.session.execute(
        db.select(GroupMember).where(
            GroupMember.id == member_id,
            GroupMember.user_id == user.id,
            GroupMember.status == GROUP_MEMBER_STATUS_INVITED,
        )
    ).scalar_one_or_none()

def invite_member(user, group, email):
    """Undang user lewat email, cuma pemilik yg boleh."""
    ensure_group_owner(user, group, "Only the group owner can send invitations")
    invited_user = db.session.execute(db.select(User).filter_by(email=normalize_email(email))).scalar_one_or_none()
    if invited_user is None or not invited_user.is_active:
        raise ValidationError([build_error("email", "No user is registered with that email")])
    if any(member.user_id == invited_user.id for member in group.member_list):
        raise ValidationError([build_error("email", "This user is already invited or already a member")])
    member = GroupMember(user_id=invited_user.id, role=GROUP_ROLE_MEMBER, status=GROUP_MEMBER_STATUS_INVITED)
    group.member_list.append(member)
    db.session.flush()
    log_audit(
        AUDIT_ACTION_CREATE, AUDIT_GROUP_MEMBER, entity_id=member.id,
        new_data_dict={"group_id": group.id, "user_email": invited_user.email, "status": member.status}, user=user,
    )
    add_notification(invited_user.id, f"{user.full_name} invited you to the group {group.name}", GROUP_LIST_PATH)
    db.session.commit()
    return member

def accept_invitation(user, invitation):
    """Terima undangan -> jadi anggota aktif."""
    if invitation.user_id != user.id or invitation.status != GROUP_MEMBER_STATUS_INVITED:
        raise PermissionDeniedError("This invitation isn't yours")
    invitation.status = GROUP_MEMBER_STATUS_ACTIVE
    log_audit(
        AUDIT_ACTION_UPDATE, AUDIT_GROUP_MEMBER, entity_id=invitation.id,
        old_data_dict={"status": GROUP_MEMBER_STATUS_INVITED}, new_data_dict={"status": GROUP_MEMBER_STATUS_ACTIVE}, user=user,
    )
    db.session.commit()
    return invitation

def decline_invitation(user, invitation):
    """Tolak undangan -> datanya dihapus."""
    if invitation.user_id != user.id or invitation.status != GROUP_MEMBER_STATUS_INVITED:
        raise PermissionDeniedError("This invitation isn't yours")
    log_audit(
        AUDIT_ACTION_DELETE, AUDIT_GROUP_MEMBER, entity_id=invitation.id,
        old_data_dict={"group_id": invitation.group_id, "status": invitation.status}, user=user,
    )
    db.session.delete(invitation)
    db.session.commit()

def detach_member(group, member):
    """Lepas anggota dari group: link punya dia dicabut, izin liat link terbatas dihapus, keanggotaannya dihapus.
    Pake DELETE langsung (jumlah query tetep, ga ngambil semua link group satu-satu). Commit di pemanggil."""
    member_entry_id_query = (
        db.select(GroupEntry.id).join(AccessEntry, AccessEntry.id == GroupEntry.access_entry_id)
        .where(GroupEntry.group_id == group.id, AccessEntry.user_id == member.user_id)
    )
    group_entry_id_query = db.select(GroupEntry.id).where(GroupEntry.group_id == group.id)
    # viewer dihapus eksplisit (ga ngandelin ON DELETE CASCADE): izin si anggota di link lain + viewer link yg dicabut
    db.session.execute(db.delete(GroupEntryViewer).where(
        GroupEntryViewer.group_entry_id.in_(group_entry_id_query),
        or_(GroupEntryViewer.user_id == member.user_id, GroupEntryViewer.group_entry_id.in_(member_entry_id_query)),
    ))
    db.session.execute(db.delete(GroupEntry).where(GroupEntry.id.in_(member_entry_id_query)))
    # koleksi yg mungkin udah kebaca di session jadi basi -> dibaca ulang kalau dipake lagi
    db.session.expire(group, ["group_entry_list"])
    group.member_list.remove(member)

def ensure_group_owner(user, group, message):
    """Aksi khusus pemilik group."""
    if not is_group_owner(user, group):
        raise PermissionDeniedError(message)

def get_non_owner_member(group, raw_member_id):
    """Anggota (bukan pemilik) di group ini, lempar ValidationError kalau ga ada."""
    member_id = parse_positive_int(raw_member_id)
    member = next((item for item in group.member_list if item.id == member_id), None)
    if member is None:
        raise ValidationError([build_error("member", "Member not found")])
    if member.role == GROUP_ROLE_OWNER:
        raise ValidationError([build_error("member", "The group owner can't be changed here")])
    return member

def remove_member(user, group, raw_member_id):
    """Keluarin anggota (atau batalin undangan), cuma pemilik."""
    ensure_group_owner(user, group, "Only the group owner can remove members")
    member = get_non_owner_member(group, raw_member_id)
    log_audit(
        AUDIT_ACTION_DELETE, AUDIT_GROUP_MEMBER, entity_id=member.id,
        old_data_dict={"group_id": group.id, "user_id": member.user_id, "status": member.status}, user=user,
    )
    # anggota aktif = dikeluarin, masih undangan = undangannya dibatalin
    if member.status == GROUP_MEMBER_STATUS_ACTIVE:
        add_notification(member.user_id, f"You were removed from the group {group.name}", GROUP_LIST_PATH)
    else:
        add_notification(member.user_id, f"Your invitation to the group {group.name} was canceled", GROUP_LIST_PATH)
    detach_member(group, member)
    db.session.commit()

def set_member_can_add_entry(user, group, raw_member_id, can_add_entry):
    """Pemilik ngasih / nyabut izin anggota buat nambah link ke group."""
    ensure_group_owner(user, group, "Only the group owner can manage member permissions")
    member = get_non_owner_member(group, raw_member_id)
    if member.can_add_entry == can_add_entry:
        return member
    log_audit(
        AUDIT_ACTION_UPDATE, AUDIT_GROUP_MEMBER, entity_id=member.id,
        old_data_dict={"group_id": group.id, "can_add_entry": member.can_add_entry},
        new_data_dict={"group_id": group.id, "can_add_entry": can_add_entry}, user=user,
    )
    member.can_add_entry = can_add_entry
    if can_add_entry:
        add_notification(member.user_id, f"You can now add links to the group {group.name}", build_group_path(group.id))
    else:
        add_notification(member.user_id, f"Your permission to add links to the group {group.name} was revoked", build_group_path(group.id))
    db.session.commit()
    return member

def leave_group(user, group):
    """Keluar dari group. Pemilik ga bisa keluar, harus hapus group-nya."""
    membership = get_group_membership(user, group)
    if membership is None:
        raise PermissionDeniedError("You are not a member of this group")
    if membership.role == GROUP_ROLE_OWNER:
        raise ValidationError([build_error("member", "The owner can't leave; delete the group if it's no longer used")])
    log_audit(
        AUDIT_ACTION_DELETE, AUDIT_GROUP_MEMBER, entity_id=membership.id,
        old_data_dict={"group_id": group.id, "user_id": user.id, "status": membership.status}, user=user,
    )
    # pemilik dikabarin ada anggota yg keluar
    add_notification(group.user_id, f"{user.full_name} left the group {group.name}", build_group_path(group.id))
    detach_member(group, membership)
    db.session.commit()

def find_group_successor(group, leaving_user_id):
    """Calon pemilik baru: anggota aktif paling lama (urut id = urut gabung), akunnya juga harus aktif."""
    return next((
        member for member in group.member_list
        if member.user_id != leaving_user_id and member.status == GROUP_MEMBER_STATUS_ACTIVE and member.user.is_active
    ), None)

def list_owned_group(user):
    """Group yg dimiliki user."""
    return db.session.execute(
        # user anggota ikut diambil: find_group_successor ngecek member.user.is_active (biar ga 1 query per anggota)
        db.select(Group).options(selectinload(Group.member_list).joinedload(GroupMember.user))
        .where(Group.user_id == user.id).order_by(Group.name)
    ).scalars().all()

def release_user_group_list(actor, user):
    """Lepas user dari semua group pas akunnya dihapus. Group miliknya pindah ke anggota terlama, kalau ga ada anggota group-nya dihapus."""
    summary_dict = {"transferred_group_id_list": [], "deleted_group_id_list": [], "left_group_id_list": []}
    membership_list = db.session.execute(
        # anggota group + user-nya ikut diambil: find_group_successor & detach_member baca itu (biar ga 1 query per anggota)
        db.select(GroupMember)
        .options(joinedload(GroupMember.group).selectinload(Group.member_list).joinedload(GroupMember.user))
        .where(GroupMember.user_id == user.id)
    ).scalars().all()
    for membership in membership_list:
        group = membership.group
        if not is_group_owner(user, group):
            detach_member(group, membership)
            summary_dict["left_group_id_list"].append(group.id)
            continue
        successor = find_group_successor(group, user.id)
        if successor is None:
            log_audit(AUDIT_ACTION_DELETE, AUDIT_GROUP, entity_id=group.id, old_data_dict=build_group_audit_dict(group), user=actor)
            db.session.delete(group)
            summary_dict["deleted_group_id_list"].append(group.id)
            continue
        log_audit(
            AUDIT_ACTION_UPDATE, AUDIT_GROUP, entity_id=group.id,
            old_data_dict={"owner_user_id": user.id}, new_data_dict={"owner_user_id": successor.user_id}, user=actor,
        )
        group.user_id = successor.user_id
        successor.role = GROUP_ROLE_OWNER
        group.member_list.remove(membership)
        summary_dict["transferred_group_id_list"].append(group.id)
    return summary_dict

def list_addable_entry(user, group):
    """Link yg boleh ditambah ke group: punya sendiri / public, dan belum ada di group."""
    already_in_group = db.select(GroupEntry.id).where(
        GroupEntry.group_id == group.id, GroupEntry.access_entry_id == AccessEntry.id,
    ).exists()
    query = (
        db.select(AccessEntry)
        .options(joinedload(AccessEntry.category))
        .where(build_shareable_entry_filter(user), ~already_in_group)
    )
    return db.session.execute(query.order_by(AccessEntry.title).limit(GROUP_ENTRY_OPTION_LIMIT)).scalars().all()

def add_group_entry(user, group, raw_entry_id):
    """Tambah link ke group (pemilik / anggota yg diizinin). Link hasil share group lain ga boleh di-share ulang."""
    if not can_add_group_entry(user, group):
        raise PermissionDeniedError("You are not allowed to add links to this group yet")
    entry_id = parse_positive_int(raw_entry_id)
    entry = None
    if entry_id is not None:
        entry = db.session.execute(
            db.select(AccessEntry).where(AccessEntry.id == entry_id, build_shareable_entry_filter(user))
        ).scalar_one_or_none()
    if entry is None:
        raise ValidationError([build_error("entry_id", "Link not found or not allowed to be shared to the group")])
    is_already_in_group = db.session.scalar(db.select(GroupEntry.id).where(
        GroupEntry.group_id == group.id, GroupEntry.access_entry_id == entry.id,
    ).limit(1)) is not None
    if is_already_in_group:
        raise ValidationError([build_error("entry_id", "This link is already in the group")])
    # ditambah lewat session (bukan group.group_entry_list.append) biar ga ngambil semua link group dulu
    group_entry = GroupEntry(group_id=group.id, access_entry_id=entry.id, user_id=user.id)
    db.session.add(group_entry)
    db.session.flush()
    log_audit(
        AUDIT_ACTION_CREATE, AUDIT_GROUP_ENTRY, entity_id=group_entry.id,
        new_data_dict={"group_id": group.id, "access_entry_id": entry.id, "title": entry.title}, user=user,
    )
    db.session.commit()
    return group_entry

def can_remove_group_entry(user, group, group_entry):
    """Boleh cabut link: pemilik group, yg nambahin, atau pemilik link-nya."""
    return (
        is_group_owner(user, group)
        or group_entry.user_id == user.id
        or group_entry.access_entry.user_id == user.id
    )

def get_group_entry(group, raw_group_entry_id):
    """Link di group ini, lempar ValidationError kalau ga ada."""
    group_entry_id = parse_positive_int(raw_group_entry_id)
    group_entry = None
    if group_entry_id is not None:
        group_entry = db.session.execute(
            db.select(GroupEntry)
            .options(selectinload(GroupEntry.viewer_list), joinedload(GroupEntry.access_entry))
            .where(GroupEntry.id == group_entry_id, GroupEntry.group_id == group.id)
        ).scalar_one_or_none()
    if group_entry is None:
        raise ValidationError([build_error("entry_id", "This link is not in the group")])
    return group_entry

def list_viewer_candidate(group):
    """Anggota aktif selain pemilik, bisa dipilih buat liat link terbatas."""
    return [
        member for member in group.member_list
        if member.status == GROUP_MEMBER_STATUS_ACTIVE and member.role != GROUP_ROLE_OWNER
    ]

def set_group_entry_viewers(user, group, raw_group_entry_id, is_restricted, raw_user_id_list):
    """Pemilik atur siapa yg bisa liat link: semua anggota, atau cuma anggota tertentu."""
    ensure_group_owner(user, group, "Only the group owner can set who can see a link")
    group_entry = get_group_entry(group, raw_group_entry_id)
    candidate_id_set = {member.user_id for member in list_viewer_candidate(group)}
    picked_id_set = {parse_positive_int(raw_user_id) for raw_user_id in raw_user_id_list or []}
    if not picked_id_set.issubset(candidate_id_set):
        raise ValidationError([build_error("viewer", "Some members are unknown")])
    viewer_id_list = sorted(picked_id_set) if is_restricted else []
    old_viewer_id_set = {viewer.user_id for viewer in group_entry.viewer_list}
    old_data_dict = {"is_restricted": group_entry.is_restricted, "viewer_user_id_list": sorted(old_viewer_id_set)}
    group_entry.is_restricted = is_restricted
    group_entry.viewer_list = [viewer for viewer in group_entry.viewer_list if viewer.user_id in viewer_id_list] + [
        GroupEntryViewer(user_id=user_id) for user_id in viewer_id_list if user_id not in old_viewer_id_set
    ]
    log_audit(
        AUDIT_ACTION_UPDATE, AUDIT_GROUP_ENTRY, entity_id=group_entry.id, old_data_dict=old_data_dict,
        new_data_dict={"is_restricted": is_restricted, "viewer_user_id_list": viewer_id_list}, user=user,
    )
    db.session.commit()
    return group_entry

def remove_group_entry(user, group, raw_group_entry_id):
    """Cabut link dari group (link aslinya ga kehapus)."""
    group_entry = get_group_entry(group, raw_group_entry_id)
    if not can_remove_group_entry(user, group, group_entry):
        raise PermissionDeniedError("You are not allowed to remove this link")
    log_audit(
        AUDIT_ACTION_DELETE, AUDIT_GROUP_ENTRY, entity_id=group_entry.id,
        old_data_dict={"group_id": group.id, "access_entry_id": group_entry.access_entry_id}, user=user,
    )
    db.session.delete(group_entry)
    db.session.commit()
