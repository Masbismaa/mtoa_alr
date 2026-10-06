"""Logika group: bikin, undang anggota, bagi link, keluar/dikeluarin."""
from sqlalchemy.orm import joinedload, selectinload
from app.extensions import db
from app.models import AccessEntry, Group, GroupEntry, GroupMember, User
from app.security.access_policy import (
    build_shareable_entry_filter,
    get_group_membership,
    is_active_group_member,
    is_group_owner,
)
from app.services.audit_service import log_audit
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
)
from app.utils.exceptions import PermissionDeniedError, ValidationError, build_error
from app.utils.query_helper import parse_positive_int
from app.utils.sanitizer import sanitize_text
from app.utils.text_helper import normalize_email

AUDIT_GROUP = "groups"
AUDIT_GROUP_MEMBER = "group_members"
AUDIT_GROUP_ENTRY = "group_entries"

def validate_group_data(data_dict):
    """Cek nama & deskripsi group, balikin data yg udah bersih."""
    clean_name = sanitize_text(data_dict.get("name"), max_length=MAX_GROUP_NAME_LENGTH)
    if not clean_name:
        raise ValidationError([build_error("name", "Nama group wajib diisi")])
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
    if not is_group_owner(user, group):
        raise PermissionDeniedError("Cuma pemilik group yang bisa mengubah group")
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
    if not is_group_owner(user, group):
        raise PermissionDeniedError("Cuma pemilik group yang bisa menghapus group")
    log_audit(AUDIT_ACTION_DELETE, AUDIT_GROUP, entity_id=group.id, old_data_dict=build_group_audit_dict(group), user=user)
    db.session.delete(group)
    db.session.commit()

def get_member_group(user, group_id):
    """Group yg user jadi anggota aktifnya. None kalau bukan anggota (jadi 404)."""
    return db.session.execute(
        db.select(Group)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .options(
            joinedload(Group.owner),
            selectinload(Group.member_list).joinedload(GroupMember.user),
            selectinload(Group.group_entry_list).options(
                joinedload(GroupEntry.added_by),
                joinedload(GroupEntry.access_entry).options(
                    joinedload(AccessEntry.category),
                    joinedload(AccessEntry.owner),
                ),
            ),
        )
        .where(
            Group.id == group_id,
            GroupMember.user_id == user.id,
            GroupMember.status == GROUP_MEMBER_STATUS_ACTIVE,
        )
    ).scalar_one_or_none()

def list_user_group(user):
    """Semua group yg user jadi anggota aktifnya."""
    return db.session.execute(
        db.select(Group)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .options(selectinload(Group.member_list), selectinload(Group.group_entry_list))
        .where(GroupMember.user_id == user.id, GroupMember.status == GROUP_MEMBER_STATUS_ACTIVE)
        .order_by(Group.name)
    ).scalars().all()

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
    if not is_group_owner(user, group):
        raise PermissionDeniedError("Cuma pemilik group yang bisa mengundang")
    invited_user = db.session.execute(db.select(User).filter_by(email=normalize_email(email))).scalar_one_or_none()
    if invited_user is None or not invited_user.is_active:
        raise ValidationError([build_error("email", "User dengan email itu belum terdaftar")])
    if any(member.user_id == invited_user.id for member in group.member_list):
        raise ValidationError([build_error("email", "User ini sudah diundang atau sudah jadi anggota")])
    member = GroupMember(user_id=invited_user.id, role=GROUP_ROLE_MEMBER, status=GROUP_MEMBER_STATUS_INVITED)
    group.member_list.append(member)
    db.session.flush()
    log_audit(
        AUDIT_ACTION_CREATE, AUDIT_GROUP_MEMBER, entity_id=member.id,
        new_data_dict={"group_id": group.id, "user_email": invited_user.email, "status": member.status}, user=user,
    )
    db.session.commit()
    return member

def accept_invitation(user, invitation):
    """Terima undangan -> jadi anggota aktif."""
    if invitation.user_id != user.id or invitation.status != GROUP_MEMBER_STATUS_INVITED:
        raise PermissionDeniedError("Undangan ini bukan punyamu")
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
        raise PermissionDeniedError("Undangan ini bukan punyamu")
    log_audit(
        AUDIT_ACTION_DELETE, AUDIT_GROUP_MEMBER, entity_id=invitation.id,
        old_data_dict={"group_id": invitation.group_id, "status": invitation.status}, user=user,
    )
    db.session.delete(invitation)
    db.session.commit()

def unshare_member_entry(group, member_user_id):
    """Cabut link punya anggota yg keluar, biar link private-nya ga ketinggalan di group."""
    for group_entry in list(group.group_entry_list):
        if group_entry.access_entry.user_id == member_user_id:
            group.group_entry_list.remove(group_entry)

def remove_member(user, group, raw_member_id):
    """Keluarin anggota (atau batalin undangan), cuma pemilik."""
    if not is_group_owner(user, group):
        raise PermissionDeniedError("Cuma pemilik group yang bisa mengeluarkan anggota")
    member_id = parse_positive_int(raw_member_id)
    member = next((item for item in group.member_list if item.id == member_id), None)
    if member is None:
        raise ValidationError([build_error("member", "Anggota tidak ditemukan")])
    if member.role == GROUP_ROLE_OWNER:
        raise ValidationError([build_error("member", "Pemilik group tidak bisa dikeluarkan")])
    unshare_member_entry(group, member.user_id)
    log_audit(
        AUDIT_ACTION_DELETE, AUDIT_GROUP_MEMBER, entity_id=member.id,
        old_data_dict={"group_id": group.id, "user_id": member.user_id, "status": member.status}, user=user,
    )
    group.member_list.remove(member)
    db.session.commit()

def leave_group(user, group):
    """Keluar dari group. Pemilik ga bisa keluar, harus hapus group-nya."""
    membership = get_group_membership(user, group)
    if membership is None:
        raise PermissionDeniedError("Kamu bukan anggota group ini")
    if membership.role == GROUP_ROLE_OWNER:
        raise ValidationError([build_error("member", "Pemilik tidak bisa keluar, hapus group-nya kalau sudah tidak dipakai")])
    unshare_member_entry(group, user.id)
    log_audit(
        AUDIT_ACTION_DELETE, AUDIT_GROUP_MEMBER, entity_id=membership.id,
        old_data_dict={"group_id": group.id, "user_id": user.id, "status": membership.status}, user=user,
    )
    group.member_list.remove(membership)
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
        db.select(Group).options(selectinload(Group.member_list)).where(Group.user_id == user.id).order_by(Group.name)
    ).scalars().all()

def release_user_group_list(actor, user):
    """Lepas user dari semua group pas akunnya dihapus. Group miliknya pindah ke anggota terlama, kalau ga ada anggota group-nya dihapus."""
    summary_dict = {"transferred_group_id_list": [], "deleted_group_id_list": [], "left_group_id_list": []}
    membership_list = db.session.execute(
        db.select(GroupMember).options(joinedload(GroupMember.group)).where(GroupMember.user_id == user.id)
    ).scalars().all()
    for membership in membership_list:
        group = membership.group
        if not is_group_owner(user, group):
            unshare_member_entry(group, user.id)
            group.member_list.remove(membership)
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
    existing_id_list = [group_entry.access_entry_id for group_entry in group.group_entry_list]
    query = (
        db.select(AccessEntry)
        .options(joinedload(AccessEntry.category))
        .where(build_shareable_entry_filter(user))
    )
    if existing_id_list:
        query = query.where(AccessEntry.id.not_in(existing_id_list))
    return db.session.execute(query.order_by(AccessEntry.title).limit(GROUP_ENTRY_OPTION_LIMIT)).scalars().all()

def add_group_entry(user, group, raw_entry_id):
    """Tambah link ke group. Link hasil share group lain ga boleh di-share ulang."""
    if not is_active_group_member(user, group):
        raise PermissionDeniedError("Kamu bukan anggota group ini")
    entry_id = parse_positive_int(raw_entry_id)
    entry = None
    if entry_id is not None:
        entry = db.session.execute(
            db.select(AccessEntry).where(AccessEntry.id == entry_id, build_shareable_entry_filter(user))
        ).scalar_one_or_none()
    if entry is None:
        raise ValidationError([build_error("entry_id", "Link tidak ditemukan atau tidak boleh dibagikan ke group")])
    if any(group_entry.access_entry_id == entry.id for group_entry in group.group_entry_list):
        raise ValidationError([build_error("entry_id", "Link ini sudah ada di group")])
    group_entry = GroupEntry(access_entry_id=entry.id, user_id=user.id)
    group.group_entry_list.append(group_entry)
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

def remove_group_entry(user, group, raw_group_entry_id):
    """Cabut link dari group (link aslinya ga kehapus)."""
    group_entry_id = parse_positive_int(raw_group_entry_id)
    group_entry = next((item for item in group.group_entry_list if item.id == group_entry_id), None)
    if group_entry is None:
        raise ValidationError([build_error("entry_id", "Link tidak ada di group ini")])
    if not can_remove_group_entry(user, group, group_entry):
        raise PermissionDeniedError("Kamu tidak boleh mencabut link ini")
    log_audit(
        AUDIT_ACTION_DELETE, AUDIT_GROUP_ENTRY, entity_id=group_entry.id,
        old_data_dict={"group_id": group.id, "access_entry_id": group_entry.access_entry_id}, user=user,
    )
    group.group_entry_list.remove(group_entry)
    db.session.commit()