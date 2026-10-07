"""Kolom tabel ala ALV per tabel: judul, lebar awal, bisa diurutin/disembunyiin atau nggak.
Layout yg disimpen user (kolom disembunyiin & lebar) dicek pake daftar ini, kolom yg ga dikenal ditolak."""
from collections import namedtuple

TABLE_ENTRY = "entry"
TABLE_USER = "user"
TABLE_AUDIT = "audit"

# width = lebar awal (px), totalnya pas di layar 1280 px biar ga perlu geser ke samping
# is_default_hidden = disembunyiin kalau user belum pernah ngatur layout
# filter_key = isian Kriteria Pencarian yg dipake filter per kolom (baris filter di bawah judul kolom), None = ga ada filter
TableColumn = namedtuple(
    "TableColumn",
    ["key", "label", "width", "is_sortable", "is_hideable", "is_default_hidden", "filter_key"],
    defaults=[True, True, False, None],
)

ENTRY_COLUMN_LIST = [
    TableColumn("title", "Judul", 180, is_hideable=False, filter_key="title"),
    TableColumn("category", "Kategori", 110, filter_key="category_id"),
    TableColumn("access", "URL / Address", 170, filter_key="access"),
    TableColumn("description", "Deskripsi", 180, is_sortable=False, is_default_hidden=True),
    TableColumn("visibility", "Visibilitas", 90, filter_key="visibility"),
    TableColumn("status", "Status Link", 110, filter_key="status"),
    TableColumn("attachment", "Lampiran", 80, is_sortable=False, is_default_hidden=True),
    TableColumn("owner", "Dibuat Oleh", 110, filter_key="owner"),
    TableColumn("created", "Dibuat", 130),
]

USER_COLUMN_LIST = [
    TableColumn("name", "User", 210, is_hideable=False, filter_key="name"),
    TableColumn("department", "Departemen", 140, filter_key="department"),
    TableColumn("role", "Role & Akses", 180, filter_key="role"),
    TableColumn("status", "Status", 100, is_sortable=False, filter_key="status"),
    TableColumn("last_login", "Login Terakhir", 120),
    TableColumn("created", "Terdaftar", 110),
]

AUDIT_COLUMN_LIST = [
    TableColumn("time", "Waktu", 170, is_hideable=False),
    TableColumn("actor", "Pelaku", 230, filter_key="actor"),
    TableColumn("action", "Aksi", 130, filter_key="action"),
    TableColumn("entity", "Data", 170, filter_key="entity_type"),
    TableColumn("ip", "IP Address", 130),
]

TABLE_COLUMN_DICT = {
    TABLE_ENTRY: ENTRY_COLUMN_LIST,
    TABLE_USER: USER_COLUMN_LIST,
    TABLE_AUDIT: AUDIT_COLUMN_LIST,
}
