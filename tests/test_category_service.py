"""Test logika kelola kategori."""
import pytest
from app.extensions import db
from app.models import AuditLog, Category
from app.services.access_entry_service import (
    create_access_entry,
    get_form_category_list,
    update_access_entry,
)
from app.services.category_service import (
    can_manage_category,
    create_category,
    create_sub_category,
    delete_category,
    list_category_summary,
    list_usable_category,
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

def test_create_category_active_and_logged(app, admin_user, category_dict):
    """Positive: sub-kategori baru langsung aktif, jadi milik pembuatnya + kecatat di audit log."""
    category = create_sub_category(admin_user, category_dict["Network"], {"name": "Database", "description": "Server DB"})
    assert category.user_id == admin_user.id
    assert category.is_active is True
    audit_log = db.session.execute(db.select(AuditLog).filter_by(entity_type="categories", entity_id=str(category.id))).scalar_one()
    assert audit_log.action == "create"

def test_create_main_category_private_to_owner(app, registered_user, other_user, category_dict):
    """Positive + negative: kategori utama bikinan user langsung aktif & kecatat di audit log, cuma pembuatnya
    yg bisa pake & kelola; akun lain boleh bikin nama yg sama buat dirinya sendiri."""
    category = create_category(registered_user, {"name": "Database", "description": "Server DB"})
    assert category.is_active is True and category.parent_id is None and category.user_id == registered_user.id
    assert category in list_usable_category(registered_user)
    assert category not in list_usable_category(other_user)
    assert can_manage_category(registered_user, category) and not can_manage_category(other_user, category)
    assert create_category(other_user, {"name": "database", "description": ""}).user_id == other_user.id
    with pytest.raises(ValidationError):
        create_category(registered_user, {"name": "DATABASE", "description": ""})
    audit_log = db.session.execute(db.select(AuditLog).filter_by(entity_type="categories", entity_id=str(category.id))).scalar_one()
    assert audit_log.action == "create"

def test_create_main_category_same_as_builtin_rejected(app, admin_user, category_dict):
    """Negative: kategori utama ga boleh kembar sama kategori bawaan, walau beda huruf besar/kecil."""
    with pytest.raises(ValidationError) as error_info:
        create_category(admin_user, {"name": "web", "description": ""})
    assert error_info.value.error_list[0]["field"] == "name"

def test_create_category_duplicate_name_ignore_case(app, admin_user, category_dict):
    """Negative: nama sama walau beda huruf besar/kecil ditolak (di induk & akun yg sama)."""
    create_sub_category(admin_user, category_dict["Network"], {"name": "Database", "description": ""})
    with pytest.raises(ValidationError) as error_info:
        create_sub_category(admin_user, category_dict["Network"], {"name": "database", "description": ""})
    assert error_info.value.error_list[0]["field"] == "name"

def test_create_category_name_too_short(app, admin_user, category_dict):
    """Negative: nama 1 huruf ditolak."""
    with pytest.raises(ValidationError):
        create_sub_category(admin_user, category_dict["Network"], {"name": "X", "description": ""})

def test_create_category_strips_html(app, admin_user, category_dict):
    """Negative (XSS): tag HTML di nama dibuang."""
    category = create_sub_category(admin_user, category_dict["Network"], {"name": "<b>Printer</b>", "description": "<script>alert(1)</script>"})
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

def test_custom_category_rename(app, admin_user, category_dict):
    """Positive: sub-kategori bikinan sendiri boleh ganti nama."""
    category = create_sub_category(admin_user, category_dict["Network"], {"name": "Databse", "description": ""})
    update_category(admin_user, category, {"name": "Database", "description": ""})
    assert category.name == "Database"

def test_default_category_cannot_be_deactivated(app, admin_user, category_dict):
    """Negative: kategori bawaan ga bisa dinonaktifin."""
    with pytest.raises(ValidationError):
        toggle_category_active(admin_user, category_dict["Network"])
    assert category_dict["Network"].is_active is True

def test_inactive_category_hidden_from_form(app, admin_user, category_dict):
    """Positive: kategori nonaktif ilang dari pilihan form tambah link."""
    category = create_sub_category(admin_user, category_dict["Network"], {"name": "Printer", "description": ""})
    toggle_category_active(admin_user, category)
    assert category.is_active is False
    assert category not in list_usable_category(admin_user)
    toggle_category_active(admin_user, category)
    assert category in list_usable_category(admin_user)

def test_create_entry_with_inactive_category_rejected(app, admin_user, category_dict):
    """Negative: link baru ga boleh pake kategori nonaktif."""
    category = create_sub_category(admin_user, category_dict["Network"], {"name": "Printer", "description": ""})
    toggle_category_active(admin_user, category)
    with pytest.raises(ValidationError) as error_info:
        create_access_entry(admin_user, build_entry_data(category))
    assert error_info.value.error_list[0]["field"] == "category_id"

def test_edit_entry_keeps_inactive_category(app, admin_user, category_dict):
    """Positive: link lama di kategori nonaktif masih bisa diedit tanpa ganti kategori."""
    category = create_sub_category(admin_user, category_dict["Network"], {"name": "Printer", "description": ""})
    entry = create_access_entry(admin_user, build_entry_data(category))
    toggle_category_active(admin_user, category)
    assert category in get_form_category_list(admin_user, entry.category)
    update_access_entry(admin_user, entry, build_entry_data(category, title="Server DB Baru"))
    assert entry.title == "Server DB Baru"
    assert entry.category_id == category.id

def test_delete_default_category_rejected(app, admin_user, category_dict):
    """Negative: kategori bawaan ga bisa dihapus."""
    with pytest.raises(ValidationError):
        delete_category(admin_user, category_dict["General"])

def test_delete_used_sub_moves_links_to_parent(app, admin_user, category_dict):
    """Positive: sub yg masih dipake link tetep bisa dihapus, link-nya (termasuk Private) pindah ke induknya."""
    category = create_sub_category(admin_user, category_dict["Network"], {"name": "Printer", "description": ""})
    entry = create_access_entry(admin_user, build_entry_data(category))
    assert delete_category(admin_user, category) == 1
    assert db.session.get(Category, category.id) is None
    db.session.refresh(entry)
    assert entry.category_id == category_dict["Network"].id

def test_delete_unused_category(app, admin_user, category_dict):
    """Positive: kategori yg belum dipake bisa dihapus + kecatat di audit log."""
    category = create_sub_category(admin_user, category_dict["Network"], {"name": "Printer", "description": ""})
    category_id = category.id
    delete_category(admin_user, category)
    assert db.session.get(Category, category_id) is None
    action_list = db.session.execute(
        db.select(AuditLog.action).filter_by(entity_type="categories", entity_id=str(category_id))
    ).scalars().all()
    assert "delete" in action_list

def test_category_summary_counts_entry(app, registered_user, other_user, category_dict):
    """Positive + negative (security): ringkasan nampilin jumlah link yg boleh diliat + tanda bawaan;
    link Private orang lain ga ikut kehitung."""
    create_access_entry(registered_user, build_entry_data(category_dict["Network"]))
    summary_dict = {summary["category"].name: summary for summary in list_category_summary(registered_user)}
    assert summary_dict["Network"]["entry_count"] == 1
    assert summary_dict["Network"]["is_default"] is True
    assert summary_dict["Network"]["can_manage"] is False
    other_summary_dict = {summary["category"].name: summary for summary in list_category_summary(other_user)}
    assert other_summary_dict["Network"]["entry_count"] == 0

def test_database_rejects_same_name_different_case(app, admin_user, registered_user, category_dict):
    """Negative (temuan audit): database sendiri nolak "sap" kalau "SAP" udah ada di induk & akun yg sama
    (biar 2 request barengan ga bisa lolos dua-duanya), tapi nama sama di induk / akun beda tetep boleh."""
    from sqlalchemy.exc import IntegrityError

    web, application = category_dict["Web"], category_dict["Application"]
    db.session.add(Category(parent_id=web.id, user_id=admin_user.id, name="SAP"))
    db.session.commit()
    db.session.add(Category(parent_id=application.id, user_id=admin_user.id, name="sap"))
    db.session.add(Category(parent_id=web.id, user_id=registered_user.id, name="sap"))
    db.session.commit()
    db.session.add(Category(parent_id=web.id, user_id=admin_user.id, name="sap"))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    db.session.add(Category(name="WEB"))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_race_on_same_category_name_gives_validation_error(app, admin_user, category_dict, monkeypatch):
    """Negative: 2 request barengan sama-sama lolos cek nama -> yg kalah dapet pesan validasi, bukan error 500."""
    from app.services import category_service

    create_sub_category(admin_user, category_dict["Network"], {"name": "Database", "description": ""})
    monkeypatch.setattr(category_service, "find_sibling_by_name", lambda *args, **kwargs: None)
    with pytest.raises(ValidationError):
        create_sub_category(admin_user, category_dict["Network"], {"name": "DATABASE", "description": ""})
