"""Test halaman group."""
from app.extensions import db
from app.models import GroupEntry, GroupMember
from app.services.access_entry_service import create_access_entry
from app.services.group_service import accept_invitation, create_group, invite_member
from app.utils.constants import GROUP_MEMBER_STATUS_INVITED, VISIBILITY_PRIVATE


def create_entry(user, category, title, url):
    """Helper: bikin link private."""
    return create_access_entry(user, {
        "category_id": category.id, "title": title, "url": url,
        "address": "", "port": "", "username": "", "access_note": "", "description": "",
        "visibility": VISIBILITY_PRIVATE,
    })


def test_groups_require_login(client):
    """Negative (security): belum login ga bisa buka group."""
    response = client.get("/groups/")
    assert response.status_code == 302
    assert "/auth/login" in response.location


def test_create_group_via_form(logged_in_client):
    """Positive: bikin group dari form -> masuk ke detail."""
    response = logged_in_client.post("/groups/new", data={"name": "Tim Server", "description": "Link server"})
    assert response.status_code == 302
    assert "Tim Server" in logged_in_client.get(response.location).get_data(as_text=True)


def test_non_member_group_returns_404(logged_in_client, other_user):
    """Negative (security): bukan anggota -> 404."""
    group = create_group(other_user, {"name": "Group Orang"})
    assert logged_in_client.get(f"/groups/{group.id}").status_code == 404


def test_member_cannot_edit_group(logged_in_client, registered_user, other_user):
    """Negative (security): anggota biasa ga bisa edit -> 403."""
    group = create_group(other_user, {"name": "Group Orang"})
    accept_invitation(registered_user, invite_member(other_user, group, registered_user.email))
    assert logged_in_client.get(f"/groups/{group.id}").status_code == 200
    assert logged_in_client.get(f"/groups/{group.id}/edit").status_code == 403


def test_invite_member_via_form(logged_in_client, registered_user, other_user):
    """Positive: undang lewat form -> status invited."""
    group = create_group(registered_user, {"name": "Tim Network"})
    response = logged_in_client.post(f"/groups/{group.id}/members", data={"email": other_user.email})
    assert response.status_code == 302
    member = db.session.execute(db.select(GroupMember).filter_by(user_id=other_user.id)).scalar_one()
    assert member.status == GROUP_MEMBER_STATUS_INVITED


def test_add_existing_entry_via_form(logged_in_client, registered_user, category_dict):
    """Positive: tambah link yg udah ada -> muncul di halaman group."""
    group = create_group(registered_user, {"name": "Tim Network"})
    entry = create_entry(registered_user, category_dict["Web"], "Portal Absensi", "https://absen.spindo.com")
    response = logged_in_client.post(f"/groups/{group.id}/entries", data={"entry_id": str(entry.id)})
    assert response.status_code == 302
    assert "Portal Absensi" in logged_in_client.get(f"/groups/{group.id}").get_data(as_text=True)


def test_create_entry_directly_into_group(logged_in_client, registered_user, category_dict):
    """Positive: tombol Link Baru di group -> abis simpan langsung masuk group."""
    group = create_group(registered_user, {"name": "Tim Network"})
    response = logged_in_client.post("/entries/new", data={
        "category_id": str(category_dict["Web"].id),
        "title": "Portal Baru",
        "url": "https://baru.spindo.com",
        "visibility": VISIBILITY_PRIVATE,
        "group_id": str(group.id),
    })
    assert response.status_code == 302
    assert f"/groups/{group.id}" in response.location
    assert db.session.execute(db.select(db.func.count(GroupEntry.id))).scalar() == 1


def test_groups_menu_available_in_sidebar(logged_in_client):
    """Positive: menu Groups di sidebar udah bisa diklik."""
    assert 'href="/groups/"' in logged_in_client.get("/").get_data(as_text=True)


def test_dashboard_counts_group(logged_in_client, registered_user):
    """Positive: kartu Group di dashboard ngitung group beneran."""
    create_group(registered_user, {"name": "Tim Network"})
    assert 'stat-card-value">1<' in logged_in_client.get("/").get_data(as_text=True)