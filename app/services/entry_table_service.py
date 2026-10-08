"""Data tabel link ala ALV yg dirender React (frontend/src/entry_table).

Satu fungsi build_entry_table_payload dipake dua kali dgn hasil yg sama persis:
  1. render awal halaman -> ditempel di atribut data-entry-table (tabel langsung tampil, ga nunggu request)
  2. API table-data -> dipanggil React tiap urutan / filter kolom / halaman berubah (tanpa reload)
Jadi aturan filter, hak akses, label, format tanggal, & URL cuma ada di Python. React cuma nampilin.

Halaman yg pake tabel ini dijelasin lewat EntryTableScope (Daftar Link & isi satu kategori).
"""
from collections import namedtuple
from urllib.parse import urlencode

from flask import url_for

from app.schemas.selection_schema import build_entry_field_list, read_entry_selection
from app.schemas.table_schema import TABLE_ENTRY
from app.services.access_entry_service import list_active_category_option, search_visible_entries
from app.services.category_service import build_category_label
from app.services.preference_service import get_table_layout
from app.utils.constants import PER_PAGE, TABLE_SORT_DESC_PREFIX, TABLE_SORT_KEY
from app.utils.data_table import build_table_view
from app.utils.datetime_helper import format_local_datetime, format_time_ago
from app.utils.query_helper import parse_positive_int
from app.utils.selection import RUN_KEY, build_selection_query_dict
from app.utils.text_helper import get_link_status_label, get_visibility_label

# id kartu tabel di halaman, dipake buat #anchor (balik dari detail langsung ke tabel)
TABLE_ANCHOR = "daftar_link"

# satu halaman yg nampilin tabel link:
# page_endpoint/api_endpoint + url_kwargs = alamat halaman & API-nya, category = None (Daftar Link) / kategori yg dibuka,
# has_sub_category = kategori itu punya sub (cuma buat teks kosong)
EntryTableScope = namedtuple("EntryTableScope", ["page_endpoint", "api_endpoint", "url_kwargs", "category", "has_sub_category"])

def build_index_scope():
    """Halaman Daftar Link: semua link yg boleh diliat, ada kolom Kategori & tombol export."""
    return EntryTableScope("entries.index", "entries.table_data", {}, None, False)

def build_category_scope(category, has_sub_category):
    """Halaman isi satu kategori: link yg ada langsung di kategori itu aja, kolom Kategori disembunyiin."""
    return EntryTableScope("categories.browse", "categories.table_data", {"category_id": category.id}, category, has_sub_category)

def build_scope_field_list(scope):
    """Isian Kriteria Pencarian halaman itu (halaman kategori ga punya isian Kategori)."""
    return build_entry_field_list(list_active_category_option() if scope.category is None else None)

def build_query_dict(args, scope, field_list):
    """Kriteria + urutan yg lagi kepake (tanpa nomor halaman). Daftar Link selalu bawa penanda Jalankan,
    soalnya tabelnya cuma tampil abis Jalankan; kalau semua filter kolom dikosongin tabelnya tetep tampil."""
    query_dict = build_selection_query_dict(args, field_list)
    if scope.category is None:
        # ditaruh paling depan biar URL-nya rapi: /entries/?run=1&sort=...
        query_dict = {RUN_KEY: ["1"], **{key: value for key, value in query_dict.items() if key != RUN_KEY}}
    return query_dict

def is_query_filtered(query_dict):
    """Ada kriteria beneran (urutan & penanda Jalankan ga diitung)."""
    return any(key not in (TABLE_SORT_KEY, RUN_KEY) for key in query_dict)

def build_page_url(scope, query_dict, page=1, anchor=TABLE_ANCHOR):
    """Alamat halaman (bukan API) dgn kriteria tertentu. Dipake buat URL di browser & tombol balik dari detail."""
    param_list = [(key, value) for key, value_list in query_dict.items() for value in value_list]
    if page > 1:
        param_list.append(("page", str(page)))
    # * (wildcard) dibiarin apa adanya, sama kayak URLSearchParams di browser, biar URL dari server & React sama persis
    query_text = urlencode(param_list, safe="*")
    base_url = url_for(scope.page_endpoint, **scope.url_kwargs)
    return f"{base_url}{'?' + query_text if query_text else ''}{'#' + anchor if anchor else ''}"

def build_access_text(entry):
    """Teks kolom URL / Address: URL, atau address(:port)."""
    if entry.url:
        return entry.url
    if not entry.address:
        return ""
    return f"{entry.address}:{entry.port}" if entry.port else entry.address

def build_status_title(entry):
    """Tooltip status: kapan terakhir dicek + catatannya."""
    part_list = []
    if entry.status_checked_at:
        part_list.append(f"Dicek {format_time_ago(entry.status_checked_at)}")
    if entry.status_note:
        part_list.append(entry.status_note)
    return " · ".join(part_list)

def build_entry_row(entry, back_url):
    """Satu baris tabel. Semua teks udah jadi (label, tanggal WIB), React tinggal nampilin."""
    return {
        "id": entry.id,
        "title": entry.title,
        "detail_url": url_for("entries.detail", entry_id=entry.id, back=back_url),
        "category_label": build_category_label(entry.category),
        "category_url": url_for("categories.browse", category_id=entry.category_id),
        "access_text": build_access_text(entry),
        "description": entry.description or "",
        "visibility": entry.visibility,
        "visibility_label": get_visibility_label(entry.visibility),
        "status": entry.status,
        "status_label": get_link_status_label(entry.status),
        "status_title": build_status_title(entry),
        "attachment_count": entry.attachment_count,
        "owner_name": entry.owner.full_name,
        "created_text": format_local_datetime(entry.created_at),
    }

def build_heading(scope, total, is_filtered):
    """Judul kartu tabel. Daftar Link nyebut jumlah di judul, halaman kategori pake badge."""
    if scope.category is not None:
        return {"icon": "link", "text": f"Link di {scope.category.name}", "count_text": f"{total} data"}
    if is_filtered:
        return {"icon": "search", "text": f"Hasil pencarian: {total} data", "count_text": None}
    return {"icon": "link", "text": f"Seluruh link: {total} data", "count_text": None}

def build_empty_state(scope, query_dict, is_filtered):
    """Isi kartu kalau ga ada data: beda antara 'ga ada yg cocok' & 'emang belum ada data'."""
    if scope.category is not None:
        category = scope.category
        if is_filtered:
            return {"icon": "search", "title": "Tidak ada link yang cocok",
                    "subtitle": "Coba ubah kriteria pencariannya, atau pakai * (misal portal*).", "action": None}
        return {
            "icon": "link", "title": "Belum ada link langsung di sini",
            "subtitle": ("Link lainnya ada di sub-kategori di atas." if scope.has_sub_category
                         else "Jadi yang pertama nambahin link di kategori ini."),
            "action": ({"url": url_for("entries.create", category_id=category.id), "label": "Tambah Link di sini",
                        "icon": "plus", "is_primary": True} if category.is_active else None),
        }
    if is_filtered:
        keyword_list = query_dict.get("q") or []
        keyword_text = f' untuk "{keyword_list[0]}"' if keyword_list else ""
        return {
            "icon": "search", "title": f"Tidak ada hasil{keyword_text}.",
            "subtitle": "Coba ubah kriteria pencariannya, atau pakai * (misal portal*).",
            "action": {"url": url_for("entries.index", run=1, _anchor=TABLE_ANCHOR), "label": "Reset filter",
                       "icon": None, "is_primary": False},
        }
    return {
        "icon": "link", "title": "Belum ada data link", "subtitle": "Yuk tambah link pertama biar tim gampang nyarinya.",
        "action": {"url": url_for("entries.create"), "label": "Tambah Link", "icon": "plus", "is_primary": True},
    }

def build_sort_text(sort):
    """Urutan aktif dalam format URL: 'title' / '-title' / '' (urutan bawaan)."""
    if sort is None:
        return ""
    return f"{TABLE_SORT_DESC_PREFIX if sort.is_desc else ''}{sort.key}"

def search_page(user, selection, scope, sort, page):
    """Ambil satu halaman data. Nomor halaman kebablasan (misal data abis dihapus) -> halaman terakhir, bukan tabel kosong."""
    search_kwargs = {
        "keyword": selection["keyword"],
        "category_id": scope.category.id if scope.category is not None else None,
        "selection": selection,
        "sort": sort,
        "per_page": PER_PAGE,
        # Daftar Link: filter kategori ikut sub-nya. Halaman kategori: link yg langsung di kategori itu aja
        "is_include_sub": scope.category is None,
    }
    pagination = search_visible_entries(user, page=page, **search_kwargs)
    if pagination.pages and page > pagination.pages:
        pagination = search_visible_entries(user, page=pagination.pages, **search_kwargs)
    return pagination

def build_entry_table_payload(user, args, scope):
    """Semua data yg dibutuhin komponen React tabel link (lihat docstring modul)."""
    field_list = build_scope_field_list(scope)
    excluded_key_list = ["category"] if scope.category is not None else []
    table_view = build_table_view(
        TABLE_ENTRY, args, get_table_layout(user, TABLE_ENTRY),
        excluded_key_list=excluded_key_list, field_list=field_list, is_run_marked=scope.category is None,
    )
    query_dict = build_query_dict(args, scope, field_list)
    is_filtered = is_query_filtered(query_dict)
    pagination = search_page(
        user, read_entry_selection(args), scope, table_view["sort"], parse_positive_int(args.get("page"), default=1),
    )
    back_url = build_page_url(scope, query_dict, pagination.page)
    has_export = scope.category is None and pagination.total > 0
    return {
        "table_key": TABLE_ENTRY,
        "api_url": url_for(scope.api_endpoint, **scope.url_kwargs),
        "page_url": url_for(scope.page_endpoint, **scope.url_kwargs),
        "layout_url": url_for("settings.update_table_layout_api"),
        "anchor": TABLE_ANCHOR,
        "columns": [
            {key: column[key] for key in ("key", "label", "width", "is_hidden", "is_sortable", "is_hideable",
                                          "sort_state", "next_sort", "filter")}
            for column in table_view["column_list"]
        ],
        "layout": table_view["layout"],
        "default_layout": table_view["default_layout"],
        "default_width_dict": table_view["default_width_dict"],
        "sort": build_sort_text(table_view["sort"]),
        "query": query_dict,
        "page": pagination.page,
        "pages": pagination.pages,
        "total": pagination.total,
        "page_list": list(pagination.iter_pages(left_edge=1, left_current=1, right_current=2, right_edge=1)),
        "rows": [build_entry_row(entry, back_url) for entry in pagination.items],
        # ada kriteria: kalau hasilnya kosong, kepala tabel (+ filter kolom) tetep tampil biar filternya bisa dihapus
        "is_filtered": is_filtered,
        "heading": build_heading(scope, pagination.total, is_filtered),
        "empty": build_empty_state(scope, query_dict, is_filtered) if not pagination.items else None,
        "export_url": url_for("main.export_entries", **query_dict) if has_export else None,
    }
