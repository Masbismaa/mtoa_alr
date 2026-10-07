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
from app.schemas.selection_schema import build_entry_field_list, read_entry_selection
from app.services.category_service import build_category_label
from app.services.dashboard_service import build_dashboard_dict
from app.services.export_service import build_entry_workbook
from app.utils.constants import (
    AUDIT_ACTION_EXPORT,
    PER_PAGE,
    EXPORT_MAX_ROW_COUNT,
    XLSX_MIMETYPE,
)
from app.utils.datetime_helper import to_local_time, utc_now
from app.utils.query_helper import parse_positive_int
from app.utils.selection import build_selection_query_dict, describe_selection
from app.utils.text_helper import get_initials
from app.utils.request_helper import get_current_user

main_bp = Blueprint("main", __name__)

def build_dashboard_field_list(category_list):
    """Isian Kriteria Pencarian Daftar Link, pilihan kategorinya dari kategori yg aktif."""
    return build_entry_field_list([(category.id, build_category_label(category)) for category in category_list])

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
    selection = read_entry_selection(request.args)
    field_list = build_dashboard_field_list(get_active_category_list())
    pagination = search_visible_entries(
        user,
        keyword=selection["keyword"],
        selection=selection,
        page=parse_positive_int(request.args.get("page"), default=1),
        per_page=PER_PAGE,
    )
    return render_template(
        "pages/home.html",
        page_title="Dashboard",
        dashboard_dict=build_dashboard_dict(user),
        pagination=pagination,
        # kriteria yg ikut kebawa pas pindah halaman & export
        pagination_query_dict=build_selection_query_dict(request.args, field_list),
        selection_field_list=field_list,
        keyword=selection["keyword"],
    )

@main_bp.get("/export")
@login_required
@limiter.limit("10 per minute")
def export_entries():
    """Download Excel daftar link sesuai filter yg lagi kepake (SR-10). Isinya cuma data yg boleh diliat user."""
    user = get_current_user()
    selection = read_entry_selection(request.args)
    entry_list, is_truncated = list_visible_entries_for_export(user, keyword=selection["keyword"], selection=selection)
    filter_text_list = describe_selection(request.args, build_dashboard_field_list(get_active_category_list()))
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
