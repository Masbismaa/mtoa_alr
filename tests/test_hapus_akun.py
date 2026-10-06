"""Test hapus akun: data Private ilang, Public tetep, group pindah/dihapus, akses dicabut, email bisa dipake lagi."""
import pytest
from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import AccessEntry, Attachment, AuditLog, Group, GroupEntry, GroupMember, OtpCode, User
from app.services import auth_service
from app.services.access_entry_service import create_access_entry
from app.services.attachment_service import get_stored_file_path
from app.services.group_service import accept_invitation, add_group_entry, create_group, invite_member, set_member_can_add_entry
from app.services.user_service import build_delete_preview, build_user_summary, delete_user_account, search_users, set_user_permissions
from app.utils.constants import (
    AUDIT_ACTION_DELETE,
    DELETED_USER_NAME,
    GROUP_ROLE_MEMBER,
    GROUP_ROLE_OWNER,
    PERMISSION_VIEW_AUDIT_LOGS,
    ROLE_ADMIN,
    VISIBILITY_PRIVATE,
    VISIBILITY_PUBLIC,
)
from app.utils.exceptions import AuthError, ValidationError

PASSWORD = "PasswordKuat123"

def create_entry(user, category, title, visibility, upload_file_list=None):
    """Helper: bikin link contoh."""
    return create_access_entry(user, {
        "category_id": category.id, "title": title, "url": f"https://{title.lower().replace(' ', '-')}.spindo.com",
        "address": "", "port": "", "username": "", "access_note": "", "description": "",
        "visibility": visibility,
    }, upload_file_list=upload_file_list)

def register(email, full_name):
    """Helper: daftar user baru."""
    return auth_service.register_user(email=email, password=PASSWORD, full_name=full_name, department="ICT", job_title="Staff")

def join_group(owner, group, member_user, can_add_entry=False):
    """Helper: undang + terima, opsional langsung dikasih izin tambah link."""
    invitation = invite_member(owner, group, member_user.email)
    accept_invitation(member_user, invitation)
    if can_add_entry:
        set_member_can_add_entry(owner, group, invitation.id, True)

def test_private_deleted_public_kept(app, admin_user, registered_user, category_dict, sample_file_dict, make_file_storage):
    """Positive: link Private + file lampirannya ilang, link Public tetep ada dgn pemilik anonim."""
    private_entry = create_entry(
        registered_user, category_dict["Web"], "Private Satu", VISIBILITY_PRIVATE,
        upload_file_list=[make_file_storage(sample_file_dict["png"], "foto.png")],
    )
    public_entry = create_entry(registered_user, category_dict["Web"], "Public Satu", VISIBILITY_PUBLIC)
    stored_path = get_stored_file_path(private_entry.attachment_list[0].stored_filename)
    private_entry_id = private_entry.id
    assert stored_path.exists()

    delete_user_account(admin_user, registered_user, "user.login@spindo.com")

    assert db.session.get(AccessEntry, private_entry_id) is None
    assert db.session.execute(db.select(Attachment)).scalars().all() == []
    assert not stored_path.exists()
    assert db.session.get(AccessEntry, public_entry.id).owner.full_name == DELETED_USER_NAME

def test_account_anonymized_and_cannot_login(app, admin_user, registered_user, fixed_otp_code):
    """Positive + security: data diri dianonimkan, password ga kepake, OTP dibuang, login ditolak."""
    auth_service.start_otp_challenge(registered_user)
    user_id = registered_user.id
    delete_user_account(admin_user, registered_user, " USER.LOGIN@spindo.com ")

    deleted_user = db.session.get(User, user_id)
    assert deleted_user.is_active is False
    assert deleted_user.deleted_at is not None
    assert deleted_user.email == f"deleted-{user_id}@deleted.invalid"
    assert deleted_user.preference is None
    assert db.session.execute(db.select(OtpCode).where(OtpCode.user_id == user_id)).scalars().all() == []
    for email in ("user.login@spindo.com", deleted_user.email):
        with pytest.raises(AuthError):
            auth_service.authenticate_user(email, PASSWORD)

def test_email_can_register_again(app, admin_user, registered_user):
    """Positive: email lama bisa dipake daftar ulang, jadi akun baru (id beda)."""
    old_id = registered_user.id
    delete_user_account(admin_user, registered_user, "user.login@spindo.com")
    new_user = register("user.login@spindo.com", "User Baru")
    assert new_user.id != old_id
    assert auth_service.authenticate_user("user.login@spindo.com", PASSWORD).id == new_user.id

def test_owned_group_moves_to_oldest_member(app, admin_user, registered_user, other_user):
    """Positive: group pindah ke anggota aktif paling lama, link Public yg dibagiin tetep ada."""
    newer_user = register("user.baru@spindo.com", "User Baru")
    group = create_group(registered_user, {"name": "Tim Network"})
    join_group(registered_user, group, other_user)
    join_group(registered_user, group, newer_user)
    group_id = group.id
    preview_dict = build_delete_preview(registered_user)
    assert preview_dict["owned_group_list"][0]["successor"].user_id == other_user.id

    delete_user_account(admin_user, registered_user, "user.login@spindo.com")

    group = db.session.get(Group, group_id)
    assert group.user_id == other_user.id
    member_role_dict = {member.user_id: member.role for member in group.member_list}
    assert member_role_dict == {other_user.id: GROUP_ROLE_OWNER, newer_user.id: GROUP_ROLE_MEMBER}

def test_owned_group_without_member_deleted(app, admin_user, registered_user, other_user):
    """Positive: group tanpa anggota aktif lain ikut dihapus (undangan yg belum diterima ga dihitung)."""
    group = create_group(registered_user, {"name": "Group Sendiri"})
    invite_member(registered_user, group, other_user.email)
    group_id = group.id
    assert build_delete_preview(registered_user)["owned_group_list"][0]["successor"] is None

    delete_user_account(admin_user, registered_user, "user.login@spindo.com")

    assert db.session.get(Group, group_id) is None
    assert db.session.execute(db.select(GroupMember).where(GroupMember.group_id == group_id)).scalars().all() == []

def test_removed_from_other_group(app, admin_user, registered_user, other_user, category_dict):
    """Positive: keluar dari group orang lain + link-nya dicabut dari group itu."""
    group = create_group(other_user, {"name": "Group Orang"})
    join_group(other_user, group, registered_user, can_add_entry=True)
    public_entry = create_entry(registered_user, category_dict["Web"], "Public Dua", VISIBILITY_PUBLIC)
    add_group_entry(registered_user, group, public_entry.id)
    user_id = registered_user.id

    delete_user_account(admin_user, registered_user, "user.login@spindo.com")

    assert db.session.execute(db.select(GroupMember).where(GroupMember.user_id == user_id)).scalars().all() == []
    assert db.session.execute(db.select(GroupEntry).where(GroupEntry.group_id == group.id)).scalars().all() == []
    assert db.session.get(AccessEntry, public_entry.id) is not None

def test_permission_revoked_and_audited(app, admin_user, registered_user):
    """Positive: akses tambahan dicabut + penghapusan kecatat di audit log (email asli ikut kecatat)."""
    set_user_permissions(admin_user, registered_user, [PERMISSION_VIEW_AUDIT_LOGS])
    delete_user_account(admin_user, registered_user, "user.login@spindo.com")

    assert registered_user.permission_list == []
    audit_log = db.session.execute(
        db.select(AuditLog).where(AuditLog.entity_type == "users", AuditLog.action == AUDIT_ACTION_DELETE)
    ).scalar_one()
    assert audit_log.user_id == admin_user.id
    assert audit_log.old_data["email"] == "user.login@spindo.com"
    assert audit_log.old_data["permission_list"] == [PERMISSION_VIEW_AUDIT_LOGS]

def test_deleted_user_hidden_from_list(app, admin_user, registered_user):
    """Positive: akun yg dihapus ga muncul di tabel & ga dihitung di ringkasan."""
    total_before = build_user_summary()["total"]
    delete_user_account(admin_user, registered_user, "user.login@spindo.com")
    assert registered_user not in search_users().items
    assert build_user_summary()["total"] == total_before - 1
    assert build_user_summary()["inactive"] == 0

@pytest.mark.parametrize("confirm_email", ["", "user.lain@spindo.com", None])
def test_wrong_confirmation_rejected(app, admin_user, registered_user, category_dict, confirm_email):
    """Negative: email konfirmasi salah/kosong -> ditolak, ga ada yg berubah."""
    entry = create_entry(registered_user, category_dict["Web"], "Private Tiga", VISIBILITY_PRIVATE)
    with pytest.raises(ValidationError):
        delete_user_account(admin_user, registered_user, confirm_email)
    assert registered_user.deleted_at is None
    assert db.session.get(AccessEntry, entry.id) is not None

def test_cannot_delete_self_or_admin(app, admin_user):
    """Negative: admin ga bisa hapus diri sendiri / admin lain."""
    other_admin = auth_service.register_user(
        email="admin.lain@spindo.com", password=PASSWORD, full_name="Admin Lain",
        department="ICT", job_title="Manager", role=ROLE_ADMIN,
    )
    with pytest.raises(ValidationError):
        delete_user_account(admin_user, admin_user, admin_user.email)
    with pytest.raises(ValidationError):
        delete_user_account(admin_user, other_admin, other_admin.email)
    assert other_admin.deleted_at is None

def test_user_entry_cannot_open_delete_page(logged_in_client, other_user):
    """Negative (RBAC): user biasa 403, akun target aman."""
    assert logged_in_client.get(f"/users/{other_user.id}/delete").status_code == 403
    assert logged_in_client.post(f"/users/{other_user.id}/delete", data={"confirm_email": other_user.email}).status_code == 403
    assert other_user.deleted_at is None

def test_admin_sees_delete_page(admin_client, registered_user):
    """Positive: halaman konfirmasi nampilin email target & dampaknya."""
    html_text = admin_client.get(f"/users/{registered_user.id}/delete").get_data(as_text=True)
    assert registered_user.email in html_text
    assert "tidak bisa dikembalikan" in html_text

def test_admin_delete_via_route(admin_client, registered_user):
    """Positive: konfirmasi bener -> akun kehapus, balik ke tabel bawa filter."""
    response = admin_client.post(
        f"/users/{registered_user.id}/delete", data={"confirm_email": registered_user.email, "back_q": "login"},
    )
    assert response.status_code == 302
    assert "q=login" in response.location
    assert registered_user.deleted_at is not None

def test_admin_wrong_email_via_route(admin_client, registered_user):
    """Negative: email salah -> tetep di halaman + pesan error."""
    response = admin_client.post(f"/users/{registered_user.id}/delete", data={"confirm_email": "salah@spindo.com"})
    assert response.status_code == 200
    assert "tidak cocok" in response.get_data(as_text=True)
    assert registered_user.deleted_at is None

def test_admin_delete_page_redirects_for_admin_target(admin_client, admin_user):
    """Negative: buka halaman hapus akun admin -> dibalikin ke tabel."""
    response = admin_client.get(f"/users/{admin_user.id}/delete")
    assert response.status_code == 302

def test_deleted_user_actions_return_404(admin_client, admin_user, registered_user):
    """Negative (security): akun yg udah dihapus ga bisa diaktifin lagi / diatur lewat URL langsung."""
    delete_user_account(admin_user, registered_user, "user.login@spindo.com")
    for path in ("toggle-active", "unlock", "delete"):
        assert admin_client.post(f"/users/{registered_user.id}/{path}").status_code == 404
    assert admin_client.get(f"/users/{registered_user.id}/access").status_code == 404
    assert registered_user.is_active is False

def test_deleted_user_logged_out_immediately(logged_in_client, admin_user, registered_user):
    """Negative (security): user yg lagi login langsung ke-logout begitu akunnya dihapus."""
    assert logged_in_client.get("/").status_code == 200
    delete_user_account(admin_user, registered_user, "user.login@spindo.com")
    response = logged_in_client.get("/")
    assert response.status_code == 302
    assert "/auth/login" in response.location

def test_delete_rate_limited(monkeypatch):
    """Negative (rate limit): kirim hapus akun lebih dari 5x per menit -> 429."""
    monkeypatch.setattr(TestingConfig, "RATELIMIT_ENABLED", True)
    monkeypatch.setattr(auth_service, "generate_otp_code", lambda: "123456")
    limited_app = create_app("testing")
    with limited_app.app_context():
        db.create_all()
        admin = auth_service.register_user(
            email="admin.limit@spindo.com", password=PASSWORD, full_name="Admin Limit",
            department="ICT", job_title="Manager", role=ROLE_ADMIN,
        )
        target = register("target.limit@spindo.com", "Target Limit")
        limited_client = limited_app.test_client()
        limited_client.post("/auth/login", data={"email": admin.email, "password": PASSWORD})
        limited_client.post("/auth/otp", data={"otp_code": "123456"})
        status_code_list = [
            limited_client.post(f"/users/{target.id}/delete", data={"confirm_email": "salah@spindo.com"}).status_code
            for _ in range(6)
        ]
        db.session.remove()
        db.drop_all()
    assert status_code_list[:5] == [200] * 5
    assert status_code_list[5] == 429
