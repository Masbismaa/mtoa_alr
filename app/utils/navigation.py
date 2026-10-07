"""Daftar menu sidebar (dikelompokin per bagian). Satu tempat, dipake layout di semua halaman."""
from flask import current_app, request, url_for

from app.security.access_policy import has_permission, is_admin
from app.utils.constants import PERMISSION_INFO_DICT, PERMISSION_MANAGE_CATEGORIES, PERMISSION_VIEW_AUDIT_LOGS

# parameter URL yg ikut nentuin menu mana yg aktif (misal filter visibilitas di dashboard)
NAV_MATCH_QUERY_KEY_LIST = ["visibility"]

# endpoint yg belum dibikin otomatis tampil "Segera" (ga bisa diklik).
# menu yg user ga punya aksesnya tetep tampil tapi dikunci (ikon gembok), biar user tau menunya ada
SIDEBAR_SECTION_LIST = [
    {"title": "Overview", "item_list": [
        {"label": "Dashboard", "endpoint": "main.home", "icon": "dashboard"},
    ]},
    {"title": "Data", "item_list": [
        {"label": "Data Link", "icon": "link", "child_list": [
            {"label": "Tambah Link", "endpoint": "entries.create"},
            {"label": "Link Public", "endpoint": "main.home", "query_dict": {"visibility": "public"}},
            {"label": "Link Private", "endpoint": "main.home", "query_dict": {"visibility": "private"}},
        ]},
        {"label": "Groups", "endpoint": "groups.index", "icon": "group"},
    ]},
    {"title": "Kelola", "item_list": [
        {"label": "Users", "endpoint": "users.index", "icon": "user", "is_admin_only": True},
        {"label": "Link Monitoring", "endpoint": "link_monitor.index", "icon": "refresh", "is_admin_only": True},
        {"label": "Categories", "endpoint": "categories.index", "icon": "category", "permission": PERMISSION_MANAGE_CATEGORIES},
        {"label": "Audit Logs", "endpoint": "audit.index", "icon": "audit", "permission": PERMISSION_VIEW_AUDIT_LOGS},
    ]},
    {"title": "Akun", "item_list": [
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

def can_open_nav_item(user, nav_item):
    """Menu bisa dibuka kalau user punya akses yg diminta menu itu."""
    if nav_item.get("is_admin_only"):
        return is_admin(user)
    permission_key = nav_item.get("permission")
    return permission_key is None or has_permission(user, permission_key)

def build_lock_reason(nav_item):
    """Keterangan kenapa menu dikunci, tampil pas kursor diarahin ke menunya."""
    if nav_item.get("is_admin_only"):
        return "Khusus admin"
    return f'Butuh akses "{PERMISSION_INFO_DICT[nav_item["permission"]]["label"]}" dari admin'

def build_sidebar_section_list(user, active_endpoint):
    """Susun semua menu per bagian + tandain yg lagi aktif & yg dikunci karena user ga punya aksesnya."""
    section_list = []
    for section in SIDEBAR_SECTION_LIST:
        item_list = []
        for nav_item in section["item_list"]:
            if not can_open_nav_item(user, nav_item):
                item_list.append({**nav_item, "is_locked": True, "lock_reason": build_lock_reason(nav_item)})
                continue
            if "child_list" in nav_item:
                child_list = [build_nav_link(child_item, active_endpoint) for child_item in nav_item["child_list"]]
                # menu induk kebuka kalau salah satu anaknya lagi aktif
                item_list.append({**nav_item, "child_list": child_list, "is_open": any(child["is_active"] for child in child_list)})
            else:
                item_list.append(build_nav_link(nav_item, active_endpoint))
        section_list.append({"title": section["title"], "item_list": item_list})
    return section_list
