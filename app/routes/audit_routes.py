"""Halaman audit log khusus admin. Cuma bisa dibaca, ga ada ubah/hapus."""
from flask import Blueprint, abort, render_template, request
from flask_login import login_required
from app.security.access_policy import can_view_audit_data
from app.security.role_guard import permission_required
from app.services.audit_service import build_audit_change_list, get_audit_log, search_audit_logs
from app.utils.constants import AUDIT_ACTION_LABEL_DICT, AUDIT_ENTITY_LABEL_DICT, PER_PAGE, PERMISSION_VIEW_AUDIT_LOGS
from app.utils.query_helper import clean_keyword_arg, drop_empty_value, parse_date_arg, parse_positive_int
from app.utils.request_helper import get_current_user

audit_bp = Blueprint("audit", __name__, url_prefix="/audit-logs")

# filter yg ikut kebawa pas pindah halaman
AUDIT_FILTER_KEY_LIST = ["action", "entity_type", "date_from", "date_to"]

def read_audit_filter():
    """Baca filter dari URL, nilai yg ngaco dicuekin aja."""
    action = request.args.get("action", "")
    entity_type = request.args.get("entity_type", "")
    return {
        "keyword": clean_keyword_arg(request.args.get("q")),
        "action": action if action in AUDIT_ACTION_LABEL_DICT else "",
        "entity_type": entity_type if entity_type in AUDIT_ENTITY_LABEL_DICT else "",
        "date_from": parse_date_arg(request.args.get("date_from")),
        "date_to": parse_date_arg(request.args.get("date_to")),
        "page": parse_positive_int(request.args.get("page"), default=1),
    }

@audit_bp.get("/")
@login_required
@permission_required(PERMISSION_VIEW_AUDIT_LOGS)
def index():
    """Tabel audit log + search, filter, dan pagination."""
    filter_dict = read_audit_filter()
    pagination = search_audit_logs(
        keyword=filter_dict["keyword"],
        action=filter_dict["action"],
        entity_type=filter_dict["entity_type"],
        date_from=filter_dict["date_from"],
        date_to=filter_dict["date_to"],
        page=filter_dict["page"],
        per_page=PER_PAGE,
    )
    pagination_query_dict = drop_empty_value({
        "q": filter_dict["keyword"],
        **{key: filter_dict[key] for key in AUDIT_FILTER_KEY_LIST},
    })
    return render_template(
        "pages/audit_logs/index.html",
        page_title="Audit Logs",
        pagination=pagination,
        pagination_query_dict=pagination_query_dict,
        filter_dict=filter_dict,
        action_label_dict=AUDIT_ACTION_LABEL_DICT,
        entity_label_dict=AUDIT_ENTITY_LABEL_DICT,
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