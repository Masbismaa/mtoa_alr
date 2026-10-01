"""Test cari audit log + susun data lama vs baru buat halaman detail."""
from datetime import date
from app.models import AuditLog
from app.services.audit_service import build_audit_change_list, format_audit_value, log_audit, search_audit_logs
from app.utils.constants import AUDIT_ACTION_CREATE, AUDIT_ACTION_LOGIN_FAILED, AUDIT_ACTION_UPDATE, MASKED_VALUE

def create_sample_logs():
    """Helper: 2 audit log beda aksi & pelaku."""
    log_audit(AUDIT_ACTION_CREATE, "groups", entity_id=1, actor_email="andi@spindo.com", is_commit=True)
    log_audit(AUDIT_ACTION_LOGIN_FAILED, "users", actor_email="budi@spindo.com", is_commit=True)

def test_search_audit_logs_filter_action_keyword_entity(app):
    """Positive: filter aksi, kata kunci, dan jenis data jalan."""
    create_sample_logs()
    assert [log.actor_email for log in search_audit_logs(action=AUDIT_ACTION_LOGIN_FAILED).items] == ["budi@spindo.com"]
    assert search_audit_logs(keyword="ANDI").total == 1
    assert search_audit_logs(entity_type="groups").total == 1

def test_search_audit_logs_newest_first(app):
    """Positive: yg terbaru di atas."""
    create_sample_logs()
    log_list = search_audit_logs().items
    assert log_list[0].id > log_list[1].id

def test_search_audit_logs_ignores_unknown_filter(app):
    """Negative: filter ngawur dicuekin, % ga jadi wildcard."""
    create_sample_logs()
    assert search_audit_logs(action="hack", entity_type="hack").total == 2
    assert search_audit_logs(keyword="%").total == 0

def test_search_audit_logs_by_date(app):
    """Positive & negative: filter tanggal (data test dibuat hari ini)."""
    create_sample_logs()
    assert search_audit_logs(date_from=date(2000, 1, 1)).total == 2
    assert search_audit_logs(date_to=date(2000, 1, 1)).total == 0

def test_build_audit_change_list_marks_changed_field(app):
    """Positive: field yg beda ditandain, yg sama nggak."""
    audit_log = AuditLog(
        action=AUDIT_ACTION_UPDATE, entity_type="groups",
        old_data={"name": "Tim Lama", "description": None},
        new_data={"name": "Tim Baru", "description": None, "password": MASKED_VALUE},
    )
    change_list = build_audit_change_list(audit_log)
    assert [change["field"] for change in change_list] == ["name", "description", "password"]
    assert change_list[0]["is_changed"] is True
    assert change_list[0]["old_value"] == "Tim Lama"
    assert change_list[1]["is_changed"] is False
    assert change_list[1]["new_value"] == "-"
    assert change_list[2]["is_masked"] is True

def test_format_audit_value():
    """Positive: nilai kebaca manusiawi."""
    assert format_audit_value(True) == "Ya"
    assert format_audit_value(False) == "Tidak"
    assert format_audit_value(["a.pdf", "b.png"]) == "a.pdf, b.png"
    assert format_audit_value([]) == "-"
    assert format_audit_value(None) == "-"
    assert format_audit_value(0) == "0"