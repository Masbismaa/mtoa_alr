"""Test kategori bertingkat: sub-kategori, batas tingkat, aturan field, filter, tampilan forum."""
import pytest
from app.services.access_entry_service import create_access_entry, get_active_category_list, search_visible_entries
from app.services.category_service import (
    build_category_label,
    build_forum_row_list,
    create_sub_category,
    delete_category,
    is_default_category,
    toggle_category_active,
    update_category,
)
from app.services.seed_service import seed_default_categories
from app.utils.constants import VISIBILITY_PRIVATE, VISIBILITY_PUBLIC
from app.utils.exceptions import PermissionDeniedError, ValidationError

def create_entry(user, category, title, visibility=VISIBILITY_PUBLIC):
    """Helper: data link, URL dibikin dari judul biar ga dobel."""
    return create_access_entry(user, {
        "category_id": category.id, "title": title, "url": f"https://{title.lower().replace(' ', '-')}.spindo.com",
        "address": "", "port": "", "username": "", "access_note": "", "description": "", "visibility": visibility,
    })

def build_sub(user, parent, name):
    """Helper: bikin sub-kategori."""
    return create_sub_category(user, parent, {"name": name, "description": ""})

def test_user_can_create_sub_category(app, registered_user, category_dict):
    """Positive: user biasa boleh bikin sub, labelnya lengkap sama induknya."""
    sap = build_sub(registered_user, category_dict["Web"], "SAP")
    assert sap.parent_id == category_dict["Web"].id
    assert sap.user_id == registered_user.id
    assert build_category_label(sap) == "Web › SAP"
    assert sap in get_active_category_list()

def test_same_name_allowed_under_different_parent(app, registered_user, category_dict):
    """Positive: Web › SAP & Application › SAP boleh barengan."""
    build_sub(registered_user, category_dict["Web"], "SAP")
    assert build_sub(registered_user, category_dict["Application"], "SAP").name == "SAP"

def test_duplicate_name_same_parent_rejected(app, registered_user, category_dict):
    """Negative: nama sama di induk yg sama ditolak (huruf besar/kecil dianggap sama)."""
    build_sub(registered_user, category_dict["Web"], "SAP")
    with pytest.raises(ValidationError):
        build_sub(registered_user, category_dict["Web"], "sap")

def test_max_four_levels(app, registered_user, category_dict):
    """Negative: kategori utama + 3 sub oke, tingkat ke-5 ditolak."""
    level_2 = build_sub(registered_user, category_dict["Web"], "SAP")
    level_3 = build_sub(registered_user, level_2, "Modul FI")
    level_4 = build_sub(registered_user, level_3, "Report")
    assert build_category_label(level_4) == "Web › SAP › Modul FI › Report"
    with pytest.raises(ValidationError):
        build_sub(registered_user, level_4, "Kedalaman")

def test_sub_under_inactive_parent_rejected(app, admin_user, registered_user, category_dict):
    """Negative: ga bisa nambah sub di kategori nonaktif, dan sub-nya ikut ilang dari pilihan."""
    sap = build_sub(registered_user, category_dict["Web"], "SAP")
    modul = build_sub(registered_user, sap, "Modul FI")
    toggle_category_active(admin_user, sap)
    assert modul not in get_active_category_list()
    with pytest.raises(ValidationError):
        build_sub(registered_user, sap, "Modul MM")

def test_sub_category_follows_root_field_rule(app, registered_user, category_dict):
    """Negative: link di Web › SAP tetep wajib URL kayak Web."""
    sap = build_sub(registered_user, category_dict["Web"], "SAP")
    with pytest.raises(ValidationError) as error_info:
        create_access_entry(registered_user, {
            "category_id": sap.id, "title": "SAP GUI", "url": "", "address": "", "port": "",
            "username": "", "access_note": "", "description": "", "visibility": VISIBILITY_PUBLIC,
        })
    assert "url" in [error_dict["field"] for error_dict in error_info.value.error_list]

def test_filter_includes_sub_category(app, registered_user, category_dict):
    """Positive: filter Web ikut nampilin link di Web › SAP, kecuali diminta langsung aja."""
    sap = build_sub(registered_user, category_dict["Web"], "SAP")
    create_entry(registered_user, category_dict["Web"], "Portal HR")
    create_entry(registered_user, sap, "SAP Fiori")
    all_title_list = [entry.title for entry in search_visible_entries(registered_user, category_id=category_dict["Web"].id).items]
    direct_title_list = [entry.title for entry in search_visible_entries(registered_user, category_id=category_dict["Web"].id, is_include_sub=False).items]
    assert sorted(all_title_list) == ["Portal HR", "SAP Fiori"]
    assert direct_title_list == ["Portal HR"]

def test_forum_count_hides_private_of_other_user(app, registered_user, other_user, category_dict):
    """Negative (security): jumlah & link terbaru di forum ga ngitung link Private orang lain."""
    sap = build_sub(registered_user, category_dict["Web"], "SAP")
    create_entry(registered_user, sap, "SAP Fiori")
    create_entry(other_user, sap, "Rahasia Orang", VISIBILITY_PRIVATE)
    row_dict = {row["category"].name: row for row in build_forum_row_list(registered_user)}
    assert row_dict["Web"]["entry_count"] == 1
    assert row_dict["Web"]["latest_entry"].title == "SAP Fiori"
    assert [sub.name for sub in row_dict["Web"]["sub_category_list"]] == ["SAP"]

def test_only_creator_or_admin_can_edit_sub(app, registered_user, other_user, admin_user, category_dict):
    """Negative (RBAC): sub bikinan orang lain ga bisa diubah, admin bisa."""
    sap = build_sub(registered_user, category_dict["Web"], "SAP")
    with pytest.raises(PermissionDeniedError):
        update_category(other_user, sap, {"name": "SAP Baru", "description": ""})
    update_category(admin_user, sap, {"name": "SAP ERP", "description": ""})
    assert sap.name == "SAP ERP"

def test_user_cannot_edit_root_category(app, registered_user, category_dict):
    """Negative (RBAC): user biasa ga bisa ubah kategori utama."""
    with pytest.raises(PermissionDeniedError):
        update_category(registered_user, category_dict["Web"], {"name": "Web", "description": "diubah"})

def test_delete_category_with_child_rejected(app, registered_user, category_dict):
    """Negative: kategori yg masih punya sub ga bisa dihapus."""
    sap = build_sub(registered_user, category_dict["Web"], "SAP")
    build_sub(registered_user, sap, "Modul FI")
    with pytest.raises(ValidationError):
        delete_category(registered_user, sap)

def test_creator_can_delete_empty_sub(app, registered_user, category_dict):
    """Positive: pembuat sub boleh hapus sub-nya yg masih kosong."""
    sap = build_sub(registered_user, category_dict["Web"], "SAP")
    delete_category(registered_user, sap)
    assert sap not in get_active_category_list()

def test_sub_named_like_default_is_not_locked(app, registered_user, category_dict):
    """Positive: sub bernama 'Web' di Network bukan kategori bawaan, & seed ga ketipu."""
    fake_web = build_sub(registered_user, category_dict["Network"], "Web")
    assert is_default_category(fake_web) is False
    assert seed_default_categories() == 0