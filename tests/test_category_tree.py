"""Test kategori bertingkat: sub-kategori pribadi per akun, batas tingkat, aturan field, filter, tampilan forum."""
import pytest
from app.services.access_entry_service import create_access_entry, search_visible_entries
from app.services.category_service import (
    build_category_label,
    build_forum_row_list,
    create_sub_category,
    delete_category,
    is_default_category,
    list_usable_category,
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
    assert sap in list_usable_category(registered_user)

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

def test_sub_under_inactive_parent_rejected(app, admin_user, category_dict):
    """Negative: ga bisa nambah sub di kategori nonaktif, dan sub-nya ikut ilang dari pilihan."""
    sap = build_sub(admin_user, category_dict["Web"], "SAP")
    modul = build_sub(admin_user, sap, "Modul FI")
    toggle_category_active(admin_user, sap)
    assert modul not in list_usable_category(admin_user)
    with pytest.raises(ValidationError):
        build_sub(admin_user, sap, "Modul MM")

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
    """Negative (security): jumlah & link terbaru di forum ga ngitung link Private orang lain, sub orang lain ga tampil."""
    sap = build_sub(registered_user, category_dict["Web"], "SAP")
    other_sap = build_sub(other_user, category_dict["Web"], "SAP Orang")
    create_entry(registered_user, sap, "SAP Fiori")
    create_entry(other_user, other_sap, "Rahasia Orang", VISIBILITY_PRIVATE)
    row_dict = {row["category"].name: row for row in build_forum_row_list(registered_user)}
    assert row_dict["Web"]["entry_count"] == 1
    assert row_dict["Web"]["latest_entry"].title == "SAP Fiori"
    assert [sub.name for sub in row_dict["Web"]["sub_category_list"]] == ["SAP"]

def test_only_creator_can_edit_sub(app, registered_user, other_user, admin_user, category_dict):
    """Negative (RBAC): sub pribadi cuma bisa diubah pembuatnya, admin pun ga bisa."""
    sap = build_sub(registered_user, category_dict["Web"], "SAP")
    for actor in (other_user, admin_user):
        with pytest.raises(PermissionDeniedError):
            update_category(actor, sap, {"name": "SAP Baru", "description": ""})
    update_category(registered_user, sap, {"name": "SAP ERP", "description": ""})
    assert sap.name == "SAP ERP"

def test_sub_category_is_private_per_account(app, admin_user, other_user, category_dict):
    """Positive + negative (security): sub-kategori cuma keliatan & kepake pembuatnya (admin juga), akun lain boleh pake
    nama sama. Link Public di sub orang lain tetep keliatan, tapi dianggap ada langsung di kategori utamanya."""
    web = category_dict["Web"]
    sap = build_sub(admin_user, web, "SAP")
    create_entry(admin_user, sap, "SAP Fiori")
    assert sap not in list_usable_category(other_user)
    assert build_sub(other_user, web, "SAP").user_id == other_user.id
    with pytest.raises(PermissionDeniedError):
        build_sub(other_user, sap, "Modul FI")
    with pytest.raises(ValidationError) as error_info:
        create_entry(other_user, sap, "Numpang")
    assert error_info.value.error_list[0]["field"] == "category_id"
    assert build_category_label(sap, other_user) == "Web"
    assert build_category_label(sap, admin_user) == "Web › SAP"
    direct_title_list = [entry.title for entry in search_visible_entries(other_user, category_id=web.id, is_include_sub=False).items]
    assert direct_title_list == ["SAP Fiori"]
    assert [entry.title for entry in search_visible_entries(admin_user, category_id=web.id, is_include_sub=False).items] == []

def test_user_cannot_edit_root_category(app, registered_user, category_dict):
    """Negative (RBAC): user biasa ga bisa ubah kategori utama."""
    with pytest.raises(PermissionDeniedError):
        update_category(registered_user, category_dict["Web"], {"name": "Web", "description": "diubah"})

def test_delete_sub_with_child_moves_all_links_to_parent(app, registered_user, category_dict):
    """Positive: sub di dalem kategori bawaan yg masih punya sub & link tetep bisa dihapus: sub di dalemnya ikut
    kehapus, semua link-nya pindah ke induk sub yg dihapus (Web), ga ada yg ilang."""
    from app.extensions import db
    from app.models import AccessEntry, Category

    web = category_dict["Web"]
    sap = build_sub(registered_user, web, "SAP")
    modul = build_sub(registered_user, sap, "Modul FI")
    report = build_sub(registered_user, modul, "Report")
    entry_id_list = [create_entry(registered_user, category, f"Link {category.name}").id for category in (sap, modul, report)]
    sub_id_list = [sap.id, modul.id, report.id]
    assert delete_category(registered_user, sap) == 3
    db.session.expire_all()
    assert all(db.session.get(Category, category_id) is None for category_id in sub_id_list)
    assert {db.session.get(AccessEntry, entry_id).category_id for entry_id in entry_id_list} == {web.id}

def test_delete_nested_sub_moves_links_to_direct_parent(app, registered_user, category_dict):
    """Positive: hapus sub tingkat dalem -> link-nya pindah ke induk langsungnya, bukan ke kategori utama."""
    sap = build_sub(registered_user, category_dict["Web"], "SAP")
    modul = build_sub(registered_user, sap, "Modul FI")
    from app.extensions import db

    entry = create_entry(registered_user, modul, "Link Modul")
    delete_category(registered_user, modul)
    db.session.refresh(entry)
    assert entry.category_id == sap.id

def test_creator_can_delete_empty_sub(app, registered_user, category_dict):
    """Positive: pembuat sub boleh hapus sub-nya yg masih kosong."""
    sap = build_sub(registered_user, category_dict["Web"], "SAP")
    delete_category(registered_user, sap)
    assert sap not in list_usable_category(registered_user)

def test_sub_named_like_default_is_not_locked(app, registered_user, category_dict):
    """Positive: sub bernama 'Web' di Network bukan kategori bawaan, & seed ga ketipu."""
    fake_web = build_sub(registered_user, category_dict["Network"], "Web")
    assert is_default_category(fake_web) is False
    assert seed_default_categories() == 0