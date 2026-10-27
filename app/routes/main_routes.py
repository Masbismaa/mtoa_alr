"""Layar awal setelah login (ALR Home), dashboard ringkasan, export Excel Daftar Link."""
import os

from flask import Blueprint, current_app, redirect, render_template, request, send_file, url_for
from flask_login import login_required
from app.extensions import limiter
from app.services.access_entry_service import (
    list_active_category_option,
    list_visible_entries_for_export,
    list_visible_favorite_entry,
)
from app.services.audit_service import log_audit
from app.schemas.selection_schema import build_entry_field_list, read_entry_selection
from app.schemas.table_schema import TABLE_COLUMN_DICT, TABLE_ENTRY
from app.services.dashboard_service import build_dashboard_dict
from app.services.export_service import build_entry_workbook
from app.utils.constants import (
    AUDIT_ACTION_EXPORT,
    EASY_ACCESS_FAVORITE_LIMIT,
    EXPORT_MAX_ROW_COUNT,
    XLSX_MIMETYPE,
)
from app.utils.data_table import read_sort
from app.utils.datetime_helper import to_local_time, utc_now
from app.utils.selection import describe_selection
from app.utils.text_helper import get_initials
from app.utils.request_helper import get_current_user

main_bp = Blueprint("main", __name__)

EASY_ACCESS_IMAGE = "images/easy_access.jpg"

def read_static_version(filename):
    """Versi file static = waktu terakhir diubah. Ditempel di URL (?v=), jadi foto yg ditimpa langsung kepake tanpa Ctrl+F5."""
    try:
        return int(os.path.getmtime(os.path.join(current_app.static_folder, filename)))
    except OSError:
        return 0

def build_export_filename(user):
    """Nama file export, misal ALR_MBP_2026-10-05.xlsx. Inisial cuma huruf/angka biar nama file aman."""
    initial_text = "".join(char for char in get_initials(user.full_name) if char.isalnum()) or "USER"
    date_text = to_local_time(utc_now()).strftime("%Y-%m-%d")
    return f"ALR_{initial_text}_{date_text}.xlsx"


@main_bp.get("/")
@login_required
def home():
    """Layar awal (Home): pohon menu (Favorites + ALR Menu) di kiri, gambar di kanan."""
    # link lama yg masih bawa kriteria (misal /?q=router) dilempar ke Daftar Link, langsung ke tabelnya.
    # query string-nya diterusin apa adanya (bukan lewat url_for, biar parameter kayak _anchor ga ikut kebaca)
    if request.query_string:
        return redirect(f"{url_for('entries.index')}?{request.query_string.decode('latin-1')}#daftar_link")
    return render_template(
        "pages/easy_access.html",
        page_title="ALR Home",
        favorite_entry_list=list_visible_favorite_entry(get_current_user(), EASY_ACCESS_FAVORITE_LIMIT),
        image_url=url_for("static", filename=EASY_ACCESS_IMAGE, v=read_static_version(EASY_ACCESS_IMAGE)),
    )

@main_bp.get("/dashboard/")
@login_required
def dashboard():
    """Dashboard (transaksi DB): ringkasan data, tindak lanjut, dan aktivitas tim. Pencarian ada di Daftar Link."""
    return render_template(
        "pages/home.html",
        page_title="Dashboard",
        dashboard_dict=build_dashboard_dict(get_current_user()),
    )

@main_bp.get("/export")
@login_required
@limiter.limit("10 per minute")
def export_entries():
    """Download Excel daftar link sesuai filter yg lagi kepake (SR-10). Isinya cuma data yg boleh diliat user."""
    user = get_current_user()
    selection = read_entry_selection(request.args)
    sort = read_sort(request.args, TABLE_COLUMN_DICT[TABLE_ENTRY])
    entry_list, is_truncated = list_visible_entries_for_export(user, keyword=selection["keyword"], selection=selection, sort=sort)
    filter_text_list = describe_selection(request.args, build_entry_field_list(list_active_category_option()))
    if is_truncated:
        filter_text_list.append(f"limited to the {EXPORT_MAX_ROW_COUNT} newest links")
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
