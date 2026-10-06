"""Halaman utama setelah login (dashboard)."""
from flask import Blueprint, render_template, request, send_file
from flask_login import login_required
from app.extensions import limiter
from app.services.access_entry_service import (
    get_active_category_list,
    list_visible_entries_for_export,
    search_visible_entries,
)
from app.services.audit_service import log_audit
from app.services.category_service import build_category_label, get_category
from app.services.dashboard_service import build_dashboard_dict
from app.services.export_service import build_entry_workbook
from app.utils.constants import (
    AUDIT_ACTION_EXPORT,
    PER_PAGE,
    EXPORT_MAX_ROW_COUNT,
    VISIBILITY_LIST,
    XLSX_MIMETYPE,
)
from app.utils.datetime_helper import to_local_time, utc_now
from app.utils.query_helper import clean_keyword_arg, drop_empty_value, parse_positive_int
from app.utils.text_helper import get_initials, get_visibility_label
from app.utils.request_helper import get_current_user

main_bp = Blueprint("main", __name__)

def read_dashboard_filter():
    """Baca filter dari URL, nilai yg ngaco dicuekin aja."""
    visibility = request.args.get("visibility", "")
    return {
        "keyword": clean_keyword_arg(request.args.get("q")),
        "category_id": parse_positive_int(request.args.get("category_id")),
        "visibility": visibility if visibility in VISIBILITY_LIST else "",
        "page": parse_positive_int(request.args.get("page"), default=1),
    }

def build_export_filename(user):
    """Nama file export, misal ALR_MBP_2026-10-05.xlsx. Inisial cuma huruf/angka biar nama file aman."""
    initial_text = "".join(char for char in get_initials(user.full_name) if char.isalnum()) or "USER"
    date_text = to_local_time(utc_now()).strftime("%Y-%m-%d")
    return f"ALR_{initial_text}_{date_text}.xlsx"


@main_bp.get("/")
@login_required
def home():
    """Dashboard: ringkasan + grafik mini + tabel link dengan search, filter, dan pagination."""
    user = get_current_user()
    filter_dict = read_dashboard_filter()
    pagination = search_visible_entries(
        user,
        keyword=filter_dict["keyword"],
        category_id=filter_dict["category_id"],
        visibility=filter_dict["visibility"],
        page=filter_dict["page"],
        per_page=PER_PAGE,
    )
    # filter yg ikut kebawa pas pindah halaman (yg kosong ga usah)
    pagination_query_dict = drop_empty_value({
        "q": filter_dict["keyword"],
        "category_id": filter_dict["category_id"],
        "visibility": filter_dict["visibility"],
    })
    return render_template(
        "pages/home.html",
        page_title="Dashboard",
        dashboard_dict=build_dashboard_dict(user),
        pagination=pagination,
        pagination_query_dict=pagination_query_dict,
        filter_dict=filter_dict,
        category_list=get_active_category_list(),
    )

def build_filter_text_list(filter_dict):
    """Filter yg lagi kepake dalam bentuk teks, ditulis di sheet Info & audit log."""
    filter_text_list = []
    if filter_dict["keyword"]:
        filter_text_list.append(f'Kata kunci "{filter_dict["keyword"]}"')
    category = get_category(filter_dict["category_id"]) if filter_dict["category_id"] else None
    if category is not None:
        filter_text_list.append(f"Kategori {build_category_label(category)} (termasuk sub)")
    if filter_dict["visibility"]:
        filter_text_list.append(f"Visibilitas {get_visibility_label(filter_dict['visibility'])}")
    return filter_text_list

@main_bp.get("/export")
@login_required
@limiter.limit("10 per minute")
def export_entries():
    """Download Excel daftar link sesuai filter yg lagi kepake (SR-10). Isinya cuma data yg boleh diliat user."""
    user = get_current_user()
    filter_dict = read_dashboard_filter()
    entry_list, is_truncated = list_visible_entries_for_export(
        user,
        keyword=filter_dict["keyword"],
        category_id=filter_dict["category_id"],
        visibility=filter_dict["visibility"],
    )
    filter_text_list = build_filter_text_list(filter_dict)
    if is_truncated:
        filter_text_list.append(f"dibatasi {EXPORT_MAX_ROW_COUNT} data terbaru")
    file_buffer = build_entry_workbook(entry_list, user, filter_text_list)
    # export dicatat, biar ketahuan siapa yg pernah narik data keluar
    log_audit(
        AUDIT_ACTION_EXPORT, "access_entries",
        new_data_dict={"row_count": len(entry_list), "filter_list": filter_text_list},
        user=user, is_commit=True,
    )
    return send_file(
        file_buffer,
        mimetype=XLSX_MIMETYPE,
        as_attachment=True,
        download_name=build_export_filename(user),
    )
