"""Kolom tabel ala ALV per tabel (judul, lebar, bisa diurut/disembunyiin)."""
from collections import namedtuple

TABLE_ENTRY = "entry"
TABLE_USER = "user"
TABLE_AUDIT = "audit"

# width = lebar awal (px), is_default_hidden = sembunyi bawaan, filter_key = isian filter kolom
TableColumn = namedtuple(
    "TableColumn",
    ["key", "label", "width", "is_sortable", "is_hideable", "is_default_hidden", "filter_key"],
    defaults=[True, True, False, None],
)

ENTRY_COLUMN_LIST = [
    TableColumn("title", "Title", 180, is_hideable=False, filter_key="title"),
    TableColumn("category", "Category", 110, filter_key="category_id"),
    TableColumn("access", "URL / Address", 170, filter_key="access"),
    TableColumn("description", "Description", 180, is_sortable=False, is_default_hidden=True),
    TableColumn("visibility", "Visibility", 90, filter_key="visibility"),
    TableColumn("status", "Link Status", 110, filter_key="status"),
    TableColumn("attachment", "Attachments", 80, is_sortable=False, is_default_hidden=True),
    TableColumn("owner", "Created By", 110, filter_key="owner"),
    TableColumn("created", "Created", 150),
]

USER_COLUMN_LIST = [
    TableColumn("name", "User", 210, is_hideable=False, filter_key="name"),
    TableColumn("department", "Department", 140, filter_key="department"),
    TableColumn("role", "Role", 180, filter_key="role"),
    TableColumn("status", "Status", 140, is_sortable=False, filter_key="status"),
    TableColumn("last_login", "Last Login", 120),
    TableColumn("created", "Created", 110),
]

AUDIT_COLUMN_LIST = [
    TableColumn("time", "Time", 170, is_hideable=False),
    TableColumn("actor", "Actor", 230, filter_key="actor"),
    TableColumn("action", "Action", 130, filter_key="action"),
    TableColumn("entity", "Data", 170, filter_key="entity_type"),
    TableColumn("ip", "IP Address", 130),
]

TABLE_COLUMN_DICT = {
    TABLE_ENTRY: ENTRY_COLUMN_LIST,
    TABLE_USER: USER_COLUMN_LIST,
    TABLE_AUDIT: AUDIT_COLUMN_LIST,
}
