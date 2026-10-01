"""Test logika kelola kategori."""
import pytest
from app.extensions import db
from app.models import AuditLog, Category
from app.services.access_entry_service import (
    create_access_entry,
    get_active_category_list,
    get_form_category_list,
    update_access_entry,
)
from app.services.category_service import (
    create_category,
    delete_category,
    list_category_summary,
    toggle_category_active,
    update_category,
)
from app.utils.constants import VISIBILITY_PRIVATE
from app.utils.exceptions import ValidationError

def build_entry_data(category, title="Server DB", visibility=VISIBILITY_PRIVATE):
    """Helper: data link minimal."""
    return {
        "category_id": category.id, "title": title, "url": "", "address": "10.0.0.5", "port": "5432",
        "username": "", "access_note": "", "description": "", "visibility": visibility,
    }

def test_create_category_active_and_logged(app, admin_user):
    """Positive: kategori baru langsung aktif + kecatat di audit log."""
    category = create_category(admin_user, {"name": "Database", "description": "Server DB"})
    assert category.is_active is True
    audit_log = db.session.execute(db.select(AuditLog).filter_by(entity_type="categories", entity_id=str(category.id))).scalar_one()
    assert audit_log.action == "create"

def test_create_category_duplicate_name_ignore_case(app, admin_user, category_dict):
    """Negative: nama sama walau beda huruf besar/kecil ditolak."""
    with pytest.raises(ValidationError) as error_info:
        create_category(admin_user, {"name": "web", "description": ""})
    assert error_info.value.error_list[0]["field"] == "name"

def test_create_category_name_too_short(app, admin_user):
    """Negative: nama 1 huruf ditolak."""
    with pytest.raises(ValidationError):
        create_category(admin_user, {"name": "X", "description": ""})

def test_create_category_strips_html(app, admin_user):
    """Negative (XSS): tag HTML di nama dibuang."""
    category = create_category(admin_user, {"name": "<b>Printer</b>", "description": "<script>alert(1)</script>"})
    assert category.name == "Printer"
    assert "<script>" not in (category.description or "")

def test_default_category_name_locked(app, admin_user, category_dict):
    """Negative: nama kategori bawaan ga bisa diganti."""
    with pytest.raises(ValidationError):
        update_category(admin_user, category_dict["Web"], {"name": "Website", "description": ""})
    assert category_dict["Web"].name == "Web"

def test_default_category_description_editable(app, admin_user, category_dict):
    """Positive: deskripsi kategori bawaan boleh diubah."""
    update_category(admin_user, category_dict["Web"], {"name": "Web", "description": "Aplikasi web kantor"})
    assert category_dict["Web"].description == "Aplikasi web kantor"

def test_custom_category_rename(app, admin_user):
    """Positive: kategori bikinan admin boleh ganti nama."""
    category = create_category(admin_user, {"name": "Databse", "description": ""})
    update_category(admin_user, category, {"name": "Database", "description": ""})
    assert category.name == "Database"

def test_default_category_cannot_be_deactivated(app, admin_user, category_dict):
    """Negative: kategori bawaan ga bisa dinonaktifin."""
    with pytest.raises(ValidationError):
        toggle_category_active(admin_user, category_dict["Network"])
    assert category_dict["Network"].is_active is True

def test_inactive_category_hidden_from_form(app, admin_user, category_dict):
    """Positive: kategori nonaktif ilang dari pilihan form tambah link."""
    category = create_category(admin_user, {"name": "Printer", "description": ""})
    toggle_category_active(admin_user, category)
    assert category.is_active is False
    assert category not in get_active_category_list()
    toggle_category_active(admin_user, category)
    assert category in get_active_category_list()

def test_create_entry_with_inactive_category_rejected(app, admin_user, registered_user, category_dict):
    """Negative: link baru ga boleh pake kategori nonaktif."""
    category = create_category(admin_user, {"name": "Printer", "description": ""})
    toggle_category_active(admin_user, category)
    with pytest.raises(ValidationError) as error_info:
        create_access_entry(registered_user, build_entry_data(category))
    assert error_info.value.error_list[0]["field"] == "category_id"

def test_edit_entry_keeps_inactive_category(app, admin_user, registered_user, category_dict):
    """Positive: link lama di kategori nonaktif masih bisa diedit tanpa ganti kategori."""
    category = create_category(admin_user, {"name": "Printer", "description": ""})
    entry = create_access_entry(registered_user, build_entry_data(category))
    toggle_category_active(admin_user, category)
    assert category in get_form_category_list(entry.category)
    update_access_entry(registered_user, entry, build_entry_data(category, title="Server DB Baru"))
    assert entry.title == "Server DB Baru"
    assert entry.category_id == category.id

def test_delete_default_category_rejected(app, admin_user, category_dict):
    """Negative: kategori bawaan ga bisa dihapus."""
    with pytest.raises(ValidationError):
        delete_category(admin_user, category_dict["General"])

def test_delete_used_category_rejected(app, admin_user, registered_user, category_dict):
    """Negative: kategori yg masih dipake link (termasuk Private) ga bisa dihapus."""
    category = create_category(admin_user, {"name": "Printer", "description": ""})
    create_access_entry(registered_user, build_entry_data(category))
    with pytest.raises(ValidationError):
        delete_category(admin_user, category)
    assert db.session.get(Category, category.id) is not None

def test_delete_unused_category(app, admin_user):
    """Positive: kategori yg belum dipake bisa dihapus + kecatat di audit log."""
    category = create_category(admin_user, {"name": "Printer", "description": ""})
    category_id = category.id
    delete_category(admin_user, category)
    assert db.session.get(Category, category_id) is None
    action_list = db.session.execute(
        db.select(AuditLog.action).filter_by(entity_type="categories", entity_id=str(category_id))
    ).scalars().all()
    assert "delete" in action_list

def test_category_summary_counts_entry(app, admin_user, registered_user, category_dict):
    """Positive: ringkasan nampilin jumlah link + tanda bawaan."""
    create_access_entry(registered_user, build_entry_data(category_dict["Network"]))
    summary_dict = {summary["category"].name: summary for summary in list_category_summary()}
    assert summary_dict["Network"]["entry_count"] == 1
    assert summary_dict["Network"]["is_default"] is True