"""Halaman audit log khusus admin. Cuma bisa dibaca, ga ada ubah/hapus."""
from flask import Blueprint, abort, render_template, request
from flask_login import login_required
from app.schemas.selection_schema import AUDIT_FIELD_LIST, read_audit_selection
from app.schemas.table_schema import TABLE_AUDIT
from app.security.access_policy import can_view_audit_data
from app.security.role_guard import permission_required
from app.services.audit_service import build_audit_change_list, get_audit_log, search_audit_logs
from app.services.preference_service import get_table_layout
from app.utils.constants import PER_PAGE, PERMISSION_VIEW_AUDIT_LOGS
from app.utils.data_table import build_table_view
from app.utils.query_helper import parse_positive_int
from app.utils.request_helper import get_current_user
from app.utils.selection import build_selection_query_dict

audit_bp = Blueprint("audit", __name__, url_prefix="/audit-logs")

@audit_bp.get("/")
@login_required
@permission_required(PERMISSION_VIEW_AUDIT_LOGS)
def index():
    """Tabel audit log + Kriteria Pencarian (Select Screen) + pagination."""
    selection = read_audit_selection(request.args)
    table_view = build_table_view(TABLE_AUDIT, request.args, get_table_layout(get_current_user(), TABLE_AUDIT), field_list=AUDIT_FIELD_LIST)
    pagination = search_audit_logs(
        keyword=selection["keyword"],
        selection=selection,
        sort=table_view["sort"],
        page=parse_positive_int(request.args.get("page"), default=1),
        per_page=PER_PAGE,
    )
    return render_template(
        "pages/audit_logs/index.html",
        page_title="Audit Logs",
        pagination=pagination,
        pagination_query_dict=build_selection_query_dict(request.args, AUDIT_FIELD_LIST),
        selection_field_list=AUDIT_FIELD_LIST,
        keyword=selection["keyword"],
        table_view=table_view,
    )

@audit_bp.get("/<int:log_id>")
@login_required
@permission_required(PERMISSION_VIEW_AUDIT_LOGS)
def detail(log_id):
    """Detail satu audit log: info pelaku + data lama vs baru."""
    audit_log = get_audit_log(log_id)
    if audit_log is None:
        abort(404)
    # data Private punya orang lain tetep ga boleh keliatan, termasuk sama admin
    is_data_visible = can_view_audit_data(get_current_user(), audit_log)
    return render_template(
        "pages/audit_logs/detail.html",
        page_title="Detail Audit Log",
        audit_log=audit_log,
        is_data_visible=is_data_visible,
        change_list=build_audit_change_list(audit_log) if is_data_visible else [],
    )
