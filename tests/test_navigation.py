"""Test menu sidebar per bagian."""
from app.utils.navigation import build_sidebar_section_list


def get_title_list(section_list):
    """Helper: judul bagian menu."""
    return [section["title"] for section in section_list]


def test_admin_section_locked_for_user(app, registered_user, admin_user):
    """Positive & negative (RBAC): bagian Kelola tampil buat semua, tapi buat user biasa menunya dikunci."""
    with app.test_request_context("/"):
        user_section_list = build_sidebar_section_list(registered_user, "main.home")
        admin_section_list = build_sidebar_section_list(admin_user, "main.home")
    assert "Manage" in get_title_list(user_section_list)
    user_manage_item_list = next(section["item_list"] for section in user_section_list if section["title"] == "Manage")
    admin_manage_item_list = next(section["item_list"] for section in admin_section_list if section["title"] == "Manage")
    assert all(item.get("is_locked") for item in user_manage_item_list)
    assert not any(item.get("is_locked") for item in admin_manage_item_list)


def test_dropdown_open_when_child_active(app, registered_user):
    """Positive: filter Link Public aktif -> menu Data Link kebuka, Dashboard ga ikut aktif."""
    with app.test_request_context("/entries/?visibility=public"):
        section_list = build_sidebar_section_list(registered_user, "entries.index")
    dashboard_item = section_list[0]["item_list"][0]
    data_link_item = section_list[1]["item_list"][0]
    assert dashboard_item["is_active"] is False
    assert data_link_item["is_open"] is True
    assert [child["label"] for child in data_link_item["child_list"] if child["is_active"]] == ["Public Links"]
    assert section_list[1]["is_open"] is True
    assert section_list[0]["is_open"] is False


def test_active_management_section_opens_only_for_authorized_user(app, registered_user, admin_user):
    with app.test_request_context("/users/"):
        admin_sections = build_sidebar_section_list(admin_user, "users.index")
        user_sections = build_sidebar_section_list(registered_user, "users.index")
    assert next(section for section in admin_sections if section["title"] == "Manage")["is_open"] is True
    assert next(section for section in user_sections if section["title"] == "Manage")["is_open"] is False
