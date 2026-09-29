"""Test angka dashboard: ngikut hak akses user."""
from app.services.access_entry_service import create_access_entry
from app.services.dashboard_service import build_dashboard_dict
from app.services.group_service import create_group, invite_member
from app.utils.constants import VISIBILITY_PRIVATE, VISIBILITY_PUBLIC


def create_entry(user, category, title, visibility):
    """Helper: bikin data link."""
    return create_access_entry(user, {
        "category_id": category.id, "title": title, "url": f"https://{title.lower().replace(' ', '-')}.spindo.com",
        "address": "", "port": "", "username": "", "access_note": "", "description": "",
        "visibility": visibility,
    })


def test_dashboard_counts_follow_access(app, registered_user, other_user, category_dict):
    """Negative (security): link Private orang lain ga ikut kehitung."""
    create_entry(registered_user, category_dict["Web"], "Punyaku Public", VISIBILITY_PUBLIC)
    create_entry(registered_user, category_dict["Web"], "Punyaku Private", VISIBILITY_PRIVATE)
    create_entry(other_user, category_dict["Web"], "Punya Orang Public", VISIBILITY_PUBLIC)
    create_entry(other_user, category_dict["Web"], "Punya Orang Private", VISIBILITY_PRIVATE)
    dashboard_dict = build_dashboard_dict(registered_user)
    assert dashboard_dict["summary"] == {"total": 3, "public": 2, "private": 1}
    assert dashboard_dict["own_count"] == 2
    assert dashboard_dict["own_percent"] == 67
    assert dashboard_dict["new_link_count"] == 3


def test_dashboard_category_and_activity(app, registered_user, category_dict):
    """Positive: jumlah per kategori & aktivitas sendiri kehitung."""
    create_entry(registered_user, category_dict["Web"], "Portal HR", VISIBILITY_PUBLIC)
    dashboard_dict = build_dashboard_dict(registered_user)
    count_by_name_dict = {card["name"]: card["count"] for card in dashboard_dict["category_card_list"]}
    assert count_by_name_dict["Web"] == 1
    assert count_by_name_dict["Network"] == 0
    assert dashboard_dict["activity_count"] >= 1
    assert dashboard_dict["recent_activity_list"][0].user_id == registered_user.id


def test_dashboard_group_and_invitation(app, registered_user, other_user):
    """Positive: group sendiri & undangan yg nunggu kehitung."""
    create_group(registered_user, {"name": "Tim Network"})
    invite_member(other_user, create_group(other_user, {"name": "Tim Server"}), registered_user.email)
    dashboard_dict = build_dashboard_dict(registered_user)
    assert [group.name for group in dashboard_dict["group_list"]] == ["Tim Network"]
    assert dashboard_dict["invitation_count"] == 1


def test_dashboard_empty_data(app, registered_user):
    """Negative: belum ada data sama sekali ga bikin error."""
    dashboard_dict = build_dashboard_dict(registered_user)
    assert dashboard_dict["summary"]["total"] == 0
    assert dashboard_dict["public_percent"] == 0
    assert dashboard_dict["new_link_change_percent"] is None
