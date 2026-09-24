"""Satu-satunya pintu buat nyatet audit log. Fitur lain tinggal panggil log_audit()."""

from app.extensions import db
from app.models import AuditLog
from app.utils.constants import AUDIT_ACTION_LIST, MASKED_VALUE, SENSITIVE_FIELD_SET
from app.utils.request_helper import get_client_ip, get_user_agent


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