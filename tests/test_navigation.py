"""Test menu sidebar per bagian."""
from app.utils.navigation import build_sidebar_section_list


def get_title_list(section_list):
    """Helper: judul bagian menu."""
    return [section["title"] for section in section_list]


def test_admin_section_only_for_admin(app, registered_user, admin_user):
    """Positive & negative (RBAC): bagian Admin cuma muncul buat admin."""
    with app.test_request_context("/"):
        assert "Admin" not in get_title_list(build_sidebar_section_list(registered_user, "main.home"))
        assert "Admin" in get_title_list(build_sidebar_section_list(admin_user, "main.home"))


def test_dropdown_open_when_child_active(app, registered_user):
    """Positive: filter Link Public aktif -> menu Data Link kebuka, Dashboard ga ikut aktif."""
    with app.test_request_context("/?visibility=public"):
        section_list = build_sidebar_section_list(registered_user, "main.home")
    dashboard_item = section_list[0]["item_list"][0]
    data_link_item = section_list[1]["item_list"][0]
    assert dashboard_item["is_active"] is False
    assert data_link_item["is_open"] is True
    assert [child["label"] for child in data_link_item["child_list"] if child["is_active"]] == ["Link Public"]
