"""Daftar menu sidebar. Satu tempat, dipake layout di semua halaman."""
from flask import current_app, url_for
from app.utils.constants import ROLE_ADMIN

# endpoint yg belum dibikin otomatis tampil "Segera" (ga bisa diklik)
SIDEBAR_NAV_ITEM_LIST = [
    {"label": "Dashboard", "endpoint": "main.home", "icon": "dashboard", "is_admin_only": False},
    {"label": "Categories", "endpoint": "categories.index", "icon": "category", "is_admin_only": True},
    {"label": "Groups", "endpoint": "groups.index", "icon": "group", "is_admin_only": False},
    {"label": "Audit Logs", "endpoint": "audit.index", "icon": "audit", "is_admin_only": True},
    {"label": "Settings", "endpoint": "settings.index", "icon": "settings", "is_admin_only": False},
]

def build_sidebar_nav_list(user, active_endpoint):
    """Susun menu sesuai role user + tandain menu yg lagi aktif."""
    view_function_dict = current_app.view_functions
    nav_list = []

    for nav_item in SIDEBAR_NAV_ITEM_LIST:
        # menu khusus admin ga ditampilin ke user biasa
        if nav_item["is_admin_only"] and user.role != ROLE_ADMIN:
            continue

        is_available = nav_item["endpoint"] in view_function_dict
        nav_list.append({
            **nav_item,
            "url": url_for(nav_item["endpoint"]) if is_available else None,
            "is_available": is_available,
            "is_active": nav_item["endpoint"] == active_endpoint,
        })
    return nav_list