"""Test audit log (SR-15): tercatat lengkap, rahasia disamarin, ga bisa diubah/dihapus."""

import pytest

from app.extensions import db
from app.models import AuditLog, User
from app.services.audit_service import log_audit
from app.utils.constants import AUDIT_ACTION_CREATE, AUDIT_ACTION_LOGIN_FAILED, MASKED_VALUE
from app.utils.exceptions import ImmutableRecordError

def create_user():
    """bikin user contoh di DB."""
    user = User(email="audit.test@spindo.com", full_name="Audit Test", department="ICT", job_title="Staff", password_hash="hash-dummy")
    db.session.add(user)
    db.session.commit()
    return user

def test_log_audit_saves_ip_and_user_agent(app):
    """IP, user agent, dan pelaku ikut kecatat."""
    user = create_user()
    with app.test_request_context("/", environ_base={"REMOTE_ADDR": "10.1.2.3"}, headers={"User-Agent": "pytest-agent"}):
        audit_log = log_audit(AUDIT_ACTION_CREATE, "access_entries", entity_id=7, user=user, is_commit=True)
    assert audit_log.id is not None
    assert audit_log.ip_address == "10.1.2.3"
    assert audit_log.user_agent == "pytest-agent"
    assert audit_log.actor_email == "audit.test@spindo.com"
    assert audit_log.entity_id == "7"

def test_log_audit_without_request_context(app):
    """dipanggil dari luar request (CLI) tetep jalan, IP-nya kosong."""
    audit_log = log_audit(AUDIT_ACTION_LOGIN_FAILED, "users", actor_email="orang.asing@spindo.com", is_commit=True)
    assert audit_log.ip_address is None
    assert audit_log.user_id is None

def test_log_audit_masks_sensitive_fields(app):
    """password & access note ga boleh kesimpen apa adanya."""
    new_data_dict = {"title": "Router Lt 2", "password": "rahasia123", "access_note": "admin/admin"}
    audit_log = log_audit(AUDIT_ACTION_CREATE, "access_entries", new_data_dict=new_data_dict, is_commit=True)
    assert audit_log.new_data["title"] == "Router Lt 2"
    assert audit_log.new_data["password"] == MASKED_VALUE
    assert audit_log.new_data["access_note"] == MASKED_VALUE

def test_log_audit_invalid_action_raises_error(app):
    """aksi ngasal ditolak."""
    with pytest.raises(ValueError):
        log_audit("hack", "users")

def test_audit_log_cannot_be_updated(app):
    """audit log yg udah kesimpen ga bisa diubah."""
    audit_log = log_audit(AUDIT_ACTION_CREATE, "categories", is_commit=True)
    audit_log.entity_type = "diubah_diam_diam"
    with pytest.raises(ImmutableRecordError):
        db.session.commit()
    db.session.rollback()

def test_audit_log_cannot_be_deleted(app):
    """audit log ga bisa dihapus."""
    audit_log = log_audit(AUDIT_ACTION_CREATE, "categories", is_commit=True)
    db.session.delete(audit_log)
    with pytest.raises(ImmutableRecordError):
        db.session.commit()
    db.session.rollback()
    assert db.session.execute(db.select(db.func.count(AuditLog.id))).scalar() == 1