"""Satu-satunya pintu buat nyatet audit log. Fitur lain tinggal panggil log_audit()."""
from app.extensions import db
from app.models import AuditLog
from app.utils.constants import (
    AUDIT_ACTION_LIST,
    AUDIT_ENTITY_LABEL_DICT,
    ENTITY_HISTORY_LIMIT,
    MASKED_VALUE,
    MAX_SEARCH_KEYWORD_LENGTH,
    PER_PAGE,
    SENSITIVE_FIELD_SET,
)
from app.utils.data_table import build_order_list
from app.utils.datetime_helper import build_utc_range_from_local_date
from app.utils.query_helper import build_keyword_filter
from app.utils.selection import apply_condition_list, build_date_range_filter, build_text_selection_filter
from app.utils.request_helper import get_client_ip, get_user_agent
from app.utils.sanitizer import sanitize_text

def mask_sensitive_data(data_dict):
    """Ganti isi field rahasia (password, access_note, dll) jadi bintang-bintang."""
    if not data_dict:
        return None
    return {
        key: MASKED_VALUE if key in SENSITIVE_FIELD_SET else value
        for key, value in data_dict.items()
    }

def log_audit(
    action,
    entity_type,
    entity_id=None,
    old_data_dict=None,
    new_data_dict=None,
    user=None,
    actor_email=None,
    is_commit=False,
):
    # tolak aksi yg ga terdaftar dari awal, jangan nunggu ditolak database
    if action not in AUDIT_ACTION_LIST:
        raise ValueError(f"Aksi audit ga dikenal: {action}")

    audit_log = AuditLog(
        user_id=user.id if user else None,
        actor_email=actor_email or (user.email if user else None),
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        old_data=mask_sensitive_data(old_data_dict),
        new_data=mask_sensitive_data(new_data_dict),
        ip_address=get_client_ip(),
        user_agent=get_user_agent(),
    )
    db.session.add(audit_log)

    if is_commit:
        db.session.commit()
    return audit_log

def apply_audit_selection(query, selection):
    """Tempel kriteria Select Screen (pelaku, aksi, jenis data, tanggal) ke query audit log."""
    return apply_condition_list(query, [
        build_text_selection_filter([AuditLog.actor_email], selection["actor"]),
        AuditLog.action.in_(selection["action_list"]) if selection["action_list"] else None,
        AuditLog.entity_type.in_(selection["entity_type_list"]) if selection["entity_type_list"] else None,
        build_date_range_filter(AuditLog.created_at, *selection["date_range"]),
    ])

# kolom yg bisa diurutin di tabel Audit Logs (kunci = key kolom di table_schema)
AUDIT_SORT_COLUMN_DICT = {
    "time": AuditLog.created_at,
    "actor": db.func.lower(AuditLog.actor_email),
    "action": AuditLog.action,
    "entity": AuditLog.entity_type,
    "ip": AuditLog.ip_address,
}

def search_audit_logs(keyword=None, action=None, entity_type=None, date_from=None, date_to=None,
                      page=1, per_page=PER_PAGE, selection=None, sort=None):
    """Cari audit log buat halaman admin, defaultnya yg terbaru di atas."""
    query = db.select(AuditLog)
    clean_keyword = sanitize_text(keyword, max_length=MAX_SEARCH_KEYWORD_LENGTH)
    if clean_keyword:
        query = query.where(build_keyword_filter([AuditLog.actor_email, AuditLog.entity_id, AuditLog.ip_address], clean_keyword))
    if action in AUDIT_ACTION_LIST:
        query = query.where(AuditLog.action == action)
    if entity_type in AUDIT_ENTITY_LABEL_DICT:
        query = query.where(AuditLog.entity_type == entity_type)
    start_at, end_at = build_utc_range_from_local_date(date_from, date_to)
    if start_at:
        query = query.where(AuditLog.created_at >= start_at)
    if end_at:
        query = query.where(AuditLog.created_at < end_at)
    if selection:
        query = apply_audit_selection(query, selection)
    default_order_list = [AuditLog.created_at.desc(), AuditLog.id.desc()]
    query = query.order_by(*build_order_list(sort, AUDIT_SORT_COLUMN_DICT, default_order_list, AuditLog.id))
    return db.paginate(query, page=page, per_page=per_page, error_out=False)

def list_entity_history(entity_type, entity_id, limit=ENTITY_HISTORY_LIMIT):
    """Riwayat satu data (misal satu link), terbaru dulu: [{audit_log, changed_field_list}].
    Isi field rahasia udah di-mask pas dicatat, di sini cuma nama field yg berubah yg ditampilin."""
    audit_log_list = db.session.execute(
        db.select(AuditLog)
        .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == str(entity_id))
        .order_by(AuditLog.id.desc())
        .limit(limit)
    ).scalars().all()
    return [
        {
            "audit_log": audit_log,
            "changed_field_list": list_changed_field(audit_log),
        }
        for audit_log in audit_log_list
    ]

def get_audit_log(log_id):
    """Ambil satu audit log, None kalau ga ada."""
    return db.session.get(AuditLog, log_id)

def list_changed_field(audit_log):
    """Nama field yg berubah (cuma buat perubahan yg punya data lama & baru). Nilainya sengaja ga ditampilin."""
    old_data_dict = audit_log.old_data or {}
    new_data_dict = audit_log.new_data or {}
    if not old_data_dict or not new_data_dict:
        return []
    # urutan field ngikutin data lama, field yg cuma ada di data baru ditaruh belakang
    field_name_list = list(old_data_dict) + [key for key in new_data_dict if key not in old_data_dict]
    return [field_name for field_name in field_name_list if old_data_dict.get(field_name) != new_data_dict.get(field_name)]
