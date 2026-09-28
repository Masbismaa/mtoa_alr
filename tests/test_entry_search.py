"""Test pencarian & filter data link di service."""
from app.services.access_entry_service import create_access_entry, search_visible_entries
from app.utils.constants import VISIBILITY_PRIVATE, VISIBILITY_PUBLIC

def build_entry_dict(category, title, url, **override_dict):
    """Helper: data link contoh."""
    entry_dict = {
        "category_id": category.id, "title": title, "url": url,
        "address": "", "port": "", "username": "", "access_note": "", "description": "",
        "visibility": VISIBILITY_PRIVATE,
    }
    entry_dict.update(override_dict)
    return entry_dict

def get_title_list(pagination):
    """Helper: judul-judul di hasil pencarian."""
    return [entry.title for entry in pagination.items]

def test_search_by_keyword_matches_title_and_url(app, registered_user, category_dict):
    """Positive: keyword cocok di judul atau URL."""
    web = category_dict["Web"]
    create_access_entry(registered_user, build_entry_dict(web, "Portal HR", "https://hr.spindo.com"))
    create_access_entry(registered_user, build_entry_dict(web, "Absensi", "https://router.spindo.com"))
    create_access_entry(registered_user, build_entry_dict(web, "Finance", "https://finance.spindo.com"))
    assert get_title_list(search_visible_entries(registered_user, keyword="portal")) == ["Portal HR"]
    assert get_title_list(search_visible_entries(registered_user, keyword="router")) == ["Absensi"]

def test_search_keyword_case_insensitive(app, registered_user, category_dict):
    """Positive: huruf besar kecil ga ngaruh."""
    create_access_entry(registered_user, build_entry_dict(category_dict["Web"], "Portal HR", "https://hr.spindo.com"))
    assert get_title_list(search_visible_entries(registered_user, keyword="PORTAL hr")) == ["Portal HR"]

def test_search_percent_sign_treated_as_text(app, registered_user, category_dict):
    """Negative (security): % di keyword dianggap huruf biasa, bukan wildcard."""
    web = category_dict["Web"]
    create_access_entry(registered_user, build_entry_dict(web, "Kapasitas 50%", "https://a.spindo.com"))
    create_access_entry(registered_user, build_entry_dict(web, "Kapasitas 500", "https://b.spindo.com"))
    assert get_title_list(search_visible_entries(registered_user, keyword="50%")) == ["Kapasitas 50%"]

def test_filter_by_category(app, registered_user, category_dict):
    """Positive: filter kategori cuma nampilin kategori itu."""
    create_access_entry(registered_user, build_entry_dict(category_dict["Web"], "Portal HR", "https://hr.spindo.com"))
    create_access_entry(registered_user, build_entry_dict(
        category_dict["Network"], "Router Lt 2", "", address="10.0.0.1", port="22",
    ))
    result = search_visible_entries(registered_user, category_id=category_dict["Network"].id)
    assert get_title_list(result) == ["Router Lt 2"]

def test_filter_by_visibility(app, registered_user, category_dict):
    """Positive: filter visibilitas."""
    web = category_dict["Web"]
    create_access_entry(registered_user, build_entry_dict(web, "Private Saya", "https://a.spindo.com"))
    create_access_entry(registered_user, build_entry_dict(web, "Public Saya", "https://b.spindo.com", visibility=VISIBILITY_PUBLIC))
    assert get_title_list(search_visible_entries(registered_user, visibility=VISIBILITY_PUBLIC)) == ["Public Saya"]

def test_search_never_returns_private_of_other_user(app, registered_user, other_user, category_dict):
    """Negative (security): keyword cocok pun, private orang lain ga muncul."""
    create_access_entry(other_user, build_entry_dict(category_dict["Web"], "Rahasia VPN", "https://vpn.spindo.com"))
    assert search_visible_entries(registered_user, keyword="vpn").total == 0

def test_pagination_per_page(app, registered_user, category_dict):
    """Positive: hasil dibagi per halaman."""
    web = category_dict["Web"]
    for index in range(3):
        create_access_entry(registered_user, build_entry_dict(web, f"Link {index}", f"https://link{index}.spindo.com"))
    first_page = search_visible_entries(registered_user, page=1, per_page=2)
    assert len(first_page.items) == 2
    assert first_page.pages == 2
    assert len(search_visible_entries(registered_user, page=2, per_page=2).items) == 1