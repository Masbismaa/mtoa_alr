"""Tabel ala ALV SAP: baca urutan dari URL, susun ORDER BY, dan siapin data kolom (lebar, disembunyiin, urutan) buat template.
Dipake bareng sama Daftar Link, Users, dan Audit Logs. Daftar kolomnya ada di app/schemas/table_schema.py."""
from collections import namedtuple
from app.schemas.table_schema import TABLE_COLUMN_DICT
from app.utils.constants import TABLE_SORT_DESC_PREFIX, TABLE_SORT_KEY
from app.utils.selection import RUN_KEY, SELECTION_CHOICE, SELECTION_TEXT, clean_value_list

SortOption = namedtuple("SortOption", ["key", "is_desc"])

def read_sort(args, column_list):
    """Urutan dari ?sort=title (naik) / ?sort=-title (turun). Kolom yg ga dikenal / ga bisa diurutin -> None (urutan bawaan)."""
    raw_value = (args.get(TABLE_SORT_KEY) or "").strip()
    is_desc = raw_value.startswith(TABLE_SORT_DESC_PREFIX)
    key = raw_value[len(TABLE_SORT_DESC_PREFIX):] if is_desc else raw_value
    sortable_key_list = [column.key for column in column_list if column.is_sortable]
    return SortOption(key, is_desc) if key in sortable_key_list else None

def build_order_list(sort, sort_column_dict, default_order_list, id_column):
    """Isi ORDER BY: kolom pilihan user (yg kosong taruh paling bawah) + id biar urutan antar halaman stabil."""
    if sort is None or sort.key not in sort_column_dict:
        return default_order_list
    column = sort_column_dict[sort.key]
    ordered_column = column.desc() if sort.is_desc else column.asc()
    return [ordered_column.nulls_last(), id_column.desc()]

def build_default_layout(table_key):
    """Layout bawaan kalau user belum pernah ngatur: kolom tertentu disembunyiin, lebar ikut daftar kolom."""
    return {
        "hidden_list": [column.key for column in TABLE_COLUMN_DICT[table_key] if column.is_default_hidden],
        "width_dict": {},
    }

def build_column_filter(args, column, field_dict):
    """Filter satu kolom (baris filter di bawah judul kolom). Pake isian Kriteria Pencarian yg sama, jadi hasilnya nyambung.
    Isian yg lagi diisi lebih dari satu nilai (lewat Multi Selection) dikunci, ngubahnya lewat Kriteria Pencarian aja."""
    field = field_dict.get(column.filter_key)
    if field is None or field.kind not in (SELECTION_TEXT, SELECTION_CHOICE):
        return None
    value_list = clean_value_list(args.getlist(field.key))
    return {
        "key": field.key,
        "kind": field.kind,
        "value": value_list[0] if value_list else "",
        "option_list": field.option_list or [],
        "is_locked": len(value_list) > 1,
    }

def build_table_view(table_key, args, layout_dict, excluded_key_list=(), field_list=(), is_run_marked=False):
    """Data kolom buat template: lebar, disembunyiin atau nggak, status urutan + nilai sort kalau judulnya diklik,
    plus filter per kolom. excluded_key_list = kolom yg emang ga ada di halaman itu (misal Kategori di halaman kategori),
    field_list = isian Kriteria Pencarian halaman itu (sumber filter per kolom),
    is_run_marked = halaman yg tabelnya baru muncul abis Jalankan (Daftar Link): filter kolom selalu bawa penanda run."""
    column_list = TABLE_COLUMN_DICT[table_key]
    field_dict = {field.key: field for field in field_list}
    sort = read_sort(args, column_list)
    hidden_list = layout_dict.get("hidden_list", [])
    width_dict = layout_dict.get("width_dict", {})
    view_column_list = []
    for column in column_list:
        if column.key in excluded_key_list:
            continue
        is_sorted = sort is not None and sort.key == column.key
        view_column_list.append({
            "key": column.key,
            "label": column.label,
            "width": width_dict.get(column.key, column.width),
            "is_hidden": column.is_hideable and column.key in hidden_list,
            "is_sortable": column.is_sortable,
            "is_hideable": column.is_hideable,
            "sort_state": ("desc" if sort.is_desc else "asc") if is_sorted else None,
            # klik pertama naik, klik lagi turun
            "next_sort": f"{TABLE_SORT_DESC_PREFIX}{column.key}" if is_sorted and not sort.is_desc else column.key,
            "filter": build_column_filter(args, column, field_dict),
        })
    # parameter lain yg lagi kepake (kriteria, urutan) ikut dikirim pas filter kolom diterapin. Halaman balik ke 1
    open_filter_key_list = [column["filter"]["key"] for column in view_column_list if column["filter"] and not column["filter"]["is_locked"]]
    filter_hidden_list = [
        (key, value) for key, value_list in args.lists() for value in value_list
        if key not in open_filter_key_list and key != "page"
    ]
    # filter kolom dikosongin semua -> tabel tetep tampil (ga balik ke layar kriteria doang)
    if is_run_marked and RUN_KEY not in args:
        filter_hidden_list.append((RUN_KEY, "1"))
    return {
        "key": table_key,
        "sort": sort,
        "column_list": view_column_list,
        "hidden_key_list": [column["key"] for column in view_column_list if column["is_hidden"]],
        "has_filter": any(column["filter"] for column in view_column_list),
        "filter_hidden_list": filter_hidden_list,
        # buat JS: layout lengkap (termasuk kolom yg ga tampil di halaman ini) & layout bawaan buat tombol reset
        "layout": {"hidden_list": hidden_list, "width_dict": width_dict},
        "default_layout": build_default_layout(table_key),
        "default_width_dict": {column.key: column.width for column in column_list},
    }
