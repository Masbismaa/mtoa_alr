"""Test notifikasi lonceng: undangan, dikeluarin, keluar group, izin tambah link, akses dari admin."""
from app.extensions import db
from app.models import UserNotification
from app.services.group_service import accept_invitation, create_group, invite_member, leave_group, remove_member, set_member_can_add_entry
from app.services.user_notification_service import add_notification, count_unread_notification
from app.services.user_service import set_user_permissions
from app.utils.constants import PERMISSION_MANAGE_CATEGORIES

def get_message_list(user):
    """Helper: isi notifikasi user, urut dari yg lama."""
    return db.session.execute(
        db.select(UserNotification.message).where(UserNotification.user_id == user.id).order_by(UserNotification.id)
    ).scalars().all()

def build_group_with_member(owner, member_user):
    """Helper: group + anggota yg udah terima undangan."""
    group = create_group(owner, {"name": "Tim Network"})
    member = invite_member(owner, group, member_user.email)
    accept_invitation(member_user, member)
    return group, member

# NOTIFIKASI DARI AKSI
def test_invite_notifies_invited_user(registered_user, other_user):
    """Positive: diundang -> yg diundang dapet notifikasi, pemilik ga."""
    group = create_group(registered_user, {"name": "Tim Network"})
    invite_member(registered_user, group, other_user.email)
    assert get_message_list(other_user) == [f"{registered_user.full_name} mengundangmu ke group Tim Network"]
    assert get_message_list(registered_user) == []

def test_remove_and_cancel_invitation_notify(registered_user, other_user):
    """Positive: anggota dikeluarin & undangan dibatalin, bunyinya beda."""
    group, member = build_group_with_member(registered_user, other_user)
    remove_member(registered_user, group, member.id)
    invitation = invite_member(registered_user, group, other_user.email)
    remove_member(registered_user, group, invitation.id)
    assert get_message_list(other_user)[1:] == [
        "Kamu dikeluarkan dari group Tim Network",
        f"{registered_user.full_name} mengundangmu ke group Tim Network",
        "Undangan ke group Tim Network dibatalkan",
    ]

def test_leave_notifies_owner(registered_user, other_user):
    """Positive: anggota keluar -> pemilik dikabarin."""
    group, _ = build_group_with_member(registered_user, other_user)
    leave_group(other_user, group)
    assert get_message_list(registered_user) == [f"{other_user.full_name} keluar dari group Tim Network"]

def test_add_entry_permission_notifies_member(registered_user, other_user):
    """Positive: izin tambah link dikasih & dicabut -> anggota dikabarin, nyimpen ulang nilai sama ga dobel."""
    group, member = build_group_with_member(registered_user, other_user)
    set_member_can_add_entry(registered_user, group, member.id, True)
    set_member_can_add_entry(registered_user, group, member.id, True)
    set_member_can_add_entry(registered_user, group, member.id, False)
    assert get_message_list(other_user)[1:] == [
        "Kamu sekarang boleh menambah link ke group Tim Network",
        "Izin menambah link ke group Tim Network dicabut",
    ]

def test_permission_grant_notifies_user(admin_user, registered_user):
    """Positive: admin ngasih & nyabut akses -> user dikabarin nama aksesnya."""
    set_user_permissions(admin_user, registered_user, [PERMISSION_MANAGE_CATEGORIES])
    set_user_permissions(admin_user, registered_user, [])
    assert get_message_list(registered_user) == ["Kamu mendapat akses: Kelola kategori", "Akses dicabut: Kelola kategori"]

# LONCENG DI LAYAR
def test_bell_shows_unread_count(logged_in_client, registered_user):
    """Positive: lonceng nampilin jumlah belum dibaca + isi notifikasi."""
    add_notification(registered_user.id, "Notifikasi <b>tes</b>", "/groups/")
    db.session.commit()
    html_text = logged_in_client.get("/").get_data(as_text=True)
    assert '<span class="badge bg-red text-red-fg badge-notification">1</span>' in html_text
    assert "Notifikasi &lt;b&gt;tes&lt;/b&gt;" in html_text

def test_open_marks_read_and_redirects(logged_in_client, registered_user):
    """Positive: klik notifikasi -> dibaca, pindah ke tujuannya."""
    notification = add_notification(registered_user.id, "Diundang", "/groups/")
    db.session.commit()
    response = logged_in_client.post(f"/notifications/{notification.id}/open", data={"back": "/entries/"})
    assert response.status_code == 302 and response.location.endswith("/groups/")
    assert count_unread_notification(registered_user) == 0

def test_open_without_target_goes_back(logged_in_client, registered_user):
    """Positive: notifikasi tanpa tujuan -> balik ke layar asal."""
    notification = add_notification(registered_user.id, "Kamu mendapat akses: Kelola kategori")
    db.session.commit()
    response = logged_in_client.post(f"/notifications/{notification.id}/open", data={"back": "/entries/?run=1"})
    assert response.location.endswith("/entries/?run=1")

def test_read_all(logged_in_client, registered_user):
    """Positive: tandain semua dibaca -> angka lonceng ilang."""
    for message in ["Satu", "Dua"]:
        add_notification(registered_user.id, message)
    db.session.commit()
    logged_in_client.post("/notifications/read-all", data={"back": "/"})
    assert count_unread_notification(registered_user) == 0
    assert "badge-notification" not in logged_in_client.get("/").get_data(as_text=True)

def test_cannot_open_other_user_notification(logged_in_client, other_user):
    """Negative (security): notifikasi punya orang lain -> 404, statusnya ga berubah."""
    notification = add_notification(other_user.id, "Rahasia")
    db.session.commit()
    assert logged_in_client.post(f"/notifications/{notification.id}/open").status_code == 404
    assert count_unread_notification(other_user) == 1

def test_back_rejects_outside_url(logged_in_client):
    """Negative (security): alamat balik ke luar ALR dicuekin, balik ke Dashboard."""
    for bad_back in ["//evil.com", "https://evil.com"]:
        response = logged_in_client.post("/notifications/read-all", data={"back": bad_back})
        assert response.location.endswith("/") and "evil.com" not in response.location

def test_notification_requires_login(client):
    """Negative (security): belum login dilempar ke halaman login."""
    response = client.post("/notifications/read-all")
    assert response.status_code == 302 and "/auth/login" in response.location
