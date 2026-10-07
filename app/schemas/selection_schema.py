"""Isian panel Kriteria Pencarian (Select Screen) per tabel + cara bacanya dari URL."""
from app.utils.constants import (
    AUDIT_ACTION_LABEL_DICT,
    AUDIT_ENTITY_LABEL_DICT,
    GROUP_ROLE_MEMBER,
    GROUP_ROLE_OWNER,
    LINK_STATUS_LABEL_DICT,
    ROLE_LABEL_DICT,
    TABLE_SORT_KEY,
    USER_STATUS_LABEL_DICT,
    VISIBILITY_LABEL_DICT,
)
from app.utils.query_helper import clean_keyword_arg
from app.utils.selection import (
    QUICK_SEARCH_KEY,
    choice_field,
    date_range_field,
    list_field_key,
    read_choice_selection,
    read_date_range,
    read_id_selection,
    read_text_selection,
    text_field,
)

# DATA LINK (dashboard, halaman kategori, export Excel)
ENTRY_CREATED_FIELD = date_range_field("created", "Tanggal Dibuat")

def build_entry_field_list(category_option_list=None):
    """Isian Daftar Link. Kategori ga ditampilin di halaman kategori (category_option_list None)."""
    field_list = [
        text_field("title", "Judul", "contoh: portal* atau *hr"),
        text_field("access", "URL / Address", "contoh: *spindo.com"),
    ]
    if category_option_list is not None:
        field_list.append(choice_field("category_id", "Kategori", category_option_list))
    return field_list + [
        choice_field("visibility", "Visibilitas", VISIBILITY_LABEL_DICT.items()),
        choice_field("status", "Status Link", LINK_STATUS_LABEL_DICT.items()),
        text_field("owner", "Dibuat Oleh", "nama atau email"),
        ENTRY_CREATED_FIELD,
    ]

def read_entry_selection(args):
    """Kriteria Daftar Link dari URL."""
    return {
        "keyword": clean_keyword_arg(args.get(QUICK_SEARCH_KEY)),
        "title": read_text_selection(args, "title"),
        "access": read_text_selection(args, "access"),
        "owner": read_text_selection(args, "owner"),
        "category_id_list": read_id_selection(args, "category_id"),
        "visibility_list": read_choice_selection(args, "visibility", VISIBILITY_LABEL_DICT),
        "status_list": read_choice_selection(args, "status", LINK_STATUS_LABEL_DICT),
        "created_range": read_date_range(args, ENTRY_CREATED_FIELD),
    }

# USERS
USER_CREATED_FIELD = date_range_field("created", "Tanggal Daftar")
USER_FIELD_LIST = [
    text_field("name", "Nama / Email", "contoh: budi* atau *@spindo.com"),
    text_field("department", "Departemen / Jabatan", "contoh: ICT"),
    choice_field("role", "Role", ROLE_LABEL_DICT.items()),
    choice_field("status", "Status Akun", USER_STATUS_LABEL_DICT.items()),
    USER_CREATED_FIELD,
]
# parameter URL tabel user (+ urutan), ikut dibawa (pake awalan back_) ke halaman/form aksi biar abis klik balik ke tampilan yg sama
USER_FILTER_KEY_LIST = ["page", QUICK_SEARCH_KEY, TABLE_SORT_KEY] + [key for field in USER_FIELD_LIST for key in list_field_key(field)]

def read_user_selection(args):
    """Kriteria tabel Users dari URL."""
    return {
        "keyword": clean_keyword_arg(args.get(QUICK_SEARCH_KEY)),
        "name": read_text_selection(args, "name"),
        "department": read_text_selection(args, "department"),
        "role_list": read_choice_selection(args, "role", ROLE_LABEL_DICT),
        "status_list": read_choice_selection(args, "status", USER_STATUS_LABEL_DICT),
        "created_range": read_date_range(args, USER_CREATED_FIELD),
    }

# AUDIT LOGS (nama parameter tanggal tetep date_from/date_to kayak sebelumnya)
AUDIT_DATE_FIELD = date_range_field("date", "Tanggal", from_key="date_from", to_key="date_to")
AUDIT_FIELD_LIST = [
    text_field("actor", "Pelaku", "email, contoh: *@spindo.com"),
    choice_field("action", "Aksi", AUDIT_ACTION_LABEL_DICT.items()),
    choice_field("entity_type", "Jenis Data", AUDIT_ENTITY_LABEL_DICT.items()),
    AUDIT_DATE_FIELD,
]

def read_audit_selection(args):
    """Kriteria Audit Logs dari URL."""
    return {
        "keyword": clean_keyword_arg(args.get(QUICK_SEARCH_KEY)),
        "actor": read_text_selection(args, "actor"),
        "action_list": read_choice_selection(args, "action", AUDIT_ACTION_LABEL_DICT),
        "entity_type_list": read_choice_selection(args, "entity_type", AUDIT_ENTITY_LABEL_DICT),
        "date_range": read_date_range(args, AUDIT_DATE_FIELD),
    }

# GROUPS
GROUP_ROLE_LABEL_DICT = {GROUP_ROLE_OWNER: "Pemilik", GROUP_ROLE_MEMBER: "Anggota"}
GROUP_FIELD_LIST = [
    text_field("name", "Nama Group", "contoh: tim*"),
    choice_field("role", "Peran Saya", GROUP_ROLE_LABEL_DICT.items()),
]

def read_group_selection(args):
    """Kriteria daftar Groups dari URL."""
    return {
        "keyword": clean_keyword_arg(args.get(QUICK_SEARCH_KEY)),
        "name": read_text_selection(args, "name"),
        "role_list": read_choice_selection(args, "role", GROUP_ROLE_LABEL_DICT),
    }
