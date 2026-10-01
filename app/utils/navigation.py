"""Daftar menu sidebar (dikelompokin per bagian). Satu tempat, dipake layout di semua halaman."""
from flask import current_app, request, url_for
from app.utils.constants import ROLE_ADMIN

# parameter URL yg ikut nentuin menu mana yg aktif (misal filter visibilitas di dashboard)
NAV_MATCH_QUERY_KEY_LIST = ["visibility"]

# endpoint yg belum dibikin otomatis tampil "Segera" (ga bisa diklik)
SIDEBAR_SECTION_LIST = [
    {"title": "Overview", "is_admin_only": False, "item_list": [
        {"label": "Dashboard", "endpoint": "main.home", "icon": "dashboard"},
    ]},
    {"title": "Data", "is_admin_only": False, "item_list": [
        {"label": "Data Link", "icon": "link", "child_list": [
            {"label": "Tambah Link", "endpoint": "entries.create"},
            {"label": "Link Public", "endpoint": "main.home", "query_dict": {"visibility": "public"}},
            {"label": "Link Private", "endpoint": "main.home", "query_dict": {"visibility": "private"}},
        ]},
        {"label": "Groups", "endpoint": "groups.index", "icon": "group"},
    ]},
    {"title": "Admin", "is_admin_only": True, "item_list": [
            {"label": "Users", "endpoint": "users.index", "icon": "user"},
            {"label": "Categories", "endpoint": "categories.index", "icon": "category"},
            {"label": "Audit Logs", "endpoint": "audit.index", "icon": "audit"},
    ]},
    {"title": "Akun", "is_admin_only": False, "item_list": [
        {"label": "Settings", "endpoint": "settings.index", "icon": "settings"},
    ]},
]


def build_nav_link(nav_item, active_endpoint):
    """Lengkapin satu menu: url, udah ada halamannya atau belum, lagi aktif atau nggak."""
    endpoint = nav_item["endpoint"]
    query_dict = nav_item.get("query_dict", {})
    is_available = endpoint in current_app.view_functions
    is_query_match = all(request.args.get(key, "") == query_dict.get(key, "") for key in NAV_MATCH_QUERY_KEY_LIST)
    return {
        **nav_item,
        "url": url_for(endpoint, **query_dict) if is_available else None,
        "is_available": is_available,
        "is_active": endpoint == active_endpoint and is_query_match,
    }


def build_sidebar_section_list(user, active_endpoint):
    """Susun menu per bagian sesuai role user + tandain menu yg lagi aktif."""
    section_list = []
    for section in SIDEBAR_SECTION_LIST:
        # bagian khusus admin ga ditampilin ke user biasa
        if section["is_admin_only"] and user.role != ROLE_ADMIN:
            continue
        item_list = []
        for nav_item in section["item_list"]:
            if "child_list" in nav_item:
                child_list = [build_nav_link(child_item, active_endpoint) for child_item in nav_item["child_list"]]
                # menu induk kebuka kalau salah satu anaknya lagi aktif
                item_list.append({**nav_item, "child_list": child_list, "is_open": any(child["is_active"] for child in child_list)})
            else:
                item_list.append(build_nav_link(nav_item, active_endpoint))
        section_list.append({"title": section["title"], "item_list": item_list})
    return section_list
