"""Test logika CRUD Access Entry"""
import pytest

from app.extensions import db
from app.models import AccessEntry, AccessEntryField, AuditLog
from app.security.encryption_service import decrypt_credential
from app.services.access_entry_service import (
    count_visible_entry_summary,
    create_access_entry,
    delete_access_entry,
    get_visible_entry,
    update_access_entry,
)
from app.utils.constants import (
    AUDIT_ACTION_CREATE,
    AUDIT_ACTION_DELETE,
    AUDIT_ACTION_UPDATE,
    CUSTOM_FIELD_MAX_COUNT,
    VISIBILITY_PRIVATE,
    VISIBILITY_PUBLIC,
)
from app.utils.exceptions import PermissionDeniedError, ValidationError


def build_entry_dict(category, **override_dict):
    """Helper: data form contoh, bisa ditimpa per test."""
    entry_dict = {
        "category_id": category.id,
        "title": "Portal HR",
        "url": "https://hr.spindo.com",
        "address": "",
        "port": "",
        "username": "",
        "access_note": "",
        "description": "",
        "visibility": VISIBILITY_PRIVATE,
    }
    entry_dict.update(override_dict)
    return entry_dict


def count_entry_audit(action):
    """Helper: hitung audit log data link dengan aksi tertentu."""
    return db.session.execute(
        db.select(db.func.count(AuditLog.id)).filter_by(action=action, entity_type="access_entries")
    ).scalar()


def get_error_field_list(error_info):
    """Helper: daftar nama field yg error."""
    return [error_dict["field"] for error_dict in error_info.value.error_list]


# create & validasi

def test_create_web_entry_success(app, registered_user, category_dict):
    """Positive: URL dirapihin, access note terenkripsi, kecatat di audit."""
    entry = create_access_entry(registered_user, build_entry_dict(
        category_dict["Web"], url="HTTPS://HR.Spindo.com/", access_note="Rahasia#123",
    ))
    assert entry.url == "https://hr.spindo.com"
    assert entry.encrypted_access_note != "Rahasia#123"
    assert decrypt_credential(entry.encrypted_access_note) == "Rahasia#123"
    assert entry.user_id == registered_user.id
    assert count_entry_audit(AUDIT_ACTION_CREATE) == 1


def test_create_web_without_url_rejected(app, registered_user, category_dict):
    """Negative: kategori Web wajib URL."""
    with pytest.raises(ValidationError) as error_info:
        create_access_entry(registered_user, build_entry_dict(category_dict["Web"], url=""))
    assert "url" in get_error_field_list(error_info)


def test_create_with_javascript_url_rejected(app, registered_user, category_dict):
    """Negative (security): URL javascript: ditolak."""
    with pytest.raises(ValidationError) as error_info:
        create_access_entry(registered_user, build_entry_dict(category_dict["Web"], url="javascript:alert(1)"))
    assert "url" in get_error_field_list(error_info)


def test_create_network_requires_address(app, registered_user, category_dict):
    """Negative: kategori Network wajib Address."""
    with pytest.raises(ValidationError) as error_info:
        create_access_entry(registered_user, build_entry_dict(category_dict["Network"], address=""))
    assert "address" in get_error_field_list(error_info)


def test_create_network_invalid_port_rejected(app, registered_user, category_dict):
    """Negative: port di luar 1-65535 ditolak."""
    with pytest.raises(ValidationError) as error_info:
        create_access_entry(registered_user, build_entry_dict(category_dict["Network"], address="10.0.0.5", port="70000"))
    assert "port" in get_error_field_list(error_info)


def test_fields_outside_category_are_cleared(app, registered_user, category_dict):
    """Positive: field yg ga dipake kategori (address di Web) otomatis dikosongin."""
    entry = create_access_entry(registered_user, build_entry_dict(category_dict["Web"], address="10.0.0.1", port="22"))
    assert entry.address is None
    assert entry.port is None


# duplikat

def test_duplicate_url_of_own_entry_rejected(app, registered_user, category_dict):
    """Negative: URL sama (beda huruf besar & garis miring) dianggap duplikat."""
    create_access_entry(registered_user, build_entry_dict(category_dict["Web"]))
    with pytest.raises(ValidationError) as error_info:
        create_access_entry(registered_user, build_entry_dict(category_dict["Web"], title="HR 2", url="https://HR.spindo.com/"))
    assert "url" in get_error_field_list(error_info)


def test_duplicate_of_public_entry_from_other_user_rejected(app, registered_user, other_user, category_dict):
    """Negative: URL yg udah ada di data public orang lain juga duplikat."""
    create_access_entry(other_user, build_entry_dict(category_dict["Web"], visibility=VISIBILITY_PUBLIC))
    with pytest.raises(ValidationError):
        create_access_entry(registered_user, build_entry_dict(category_dict["Web"]))


def test_private_entry_of_other_user_not_counted_as_duplicate(app, registered_user, other_user, category_dict):
    """Positive (security): private orang lain ga ikut dicek, biar keberadaannya ga bocor."""
    create_access_entry(other_user, build_entry_dict(category_dict["Web"], visibility=VISIBILITY_PRIVATE))
    entry = create_access_entry(registered_user, build_entry_dict(category_dict["Web"]))
    assert entry.id is not None


def test_duplicate_address_and_port_rejected(app, registered_user, category_dict):
    """Negative: kombinasi Address + Port yg sama ditolak."""
    network_dict = build_entry_dict(category_dict["Network"], address="10.0.0.1", port="22")
    create_access_entry(registered_user, network_dict)
    with pytest.raises(ValidationError) as error_info:
        create_access_entry(registered_user, {**network_dict, "title": "Router lain"})
    assert "address" in get_error_field_list(error_info)


# field tambahan (General)

def test_general_custom_fields_saved_sanitized_and_ordered(app, registered_user, category_dict):
    """Positive (revisi): field tambahan kesimpen urut & isinya udah dibersihin."""
    pair_list = [("Langkah VPN", "<b>Buka</b> FortiClient<script>alert(1)</script>"), ("Kontak", "<p>Ext 123</p>")]
    entry = create_access_entry(registered_user, build_entry_dict(category_dict["General"], title="Panduan VPN"), pair_list)
    label_list = [field.field_label for field in entry.custom_field_list]
    assert label_list == ["Langkah VPN", "Kontak"]
    assert "<b>Buka</b>" in entry.custom_field_list[0].field_content
    assert "script" not in entry.custom_field_list[0].field_content
    assert [field.sort_order for field in entry.custom_field_list] == [1, 2]


def test_general_custom_field_without_label_rejected(app, registered_user, category_dict):
    """Negative: judul field tambahan wajib diisi."""
    with pytest.raises(ValidationError) as error_info:
        create_access_entry(registered_user, build_entry_dict(category_dict["General"]), [("", "<p>isi</p>")])
    assert "custom_field" in get_error_field_list(error_info)


def test_general_custom_field_over_limit_rejected(app, registered_user, category_dict):
    """Negative: lebih dari batas pengaman ditolak."""
    pair_list = [("Field", "<p>isi</p>")] * (CUSTOM_FIELD_MAX_COUNT + 1)
    with pytest.raises(ValidationError) as error_info:
        create_access_entry(registered_user, build_entry_dict(category_dict["General"]), pair_list)
    assert "custom_field" in get_error_field_list(error_info)


def test_custom_fields_ignored_for_web(app, registered_user, category_dict):
    """Positive: kategori selain General ga nyimpen field tambahan."""
    entry = create_access_entry(registered_user, build_entry_dict(category_dict["Web"]), [("Judul", "<p>isi</p>")])
    assert entry.custom_field_list == []


# update & delete

def test_update_by_owner_success(app, registered_user, category_dict):
    """Positive: pemilik bisa ubah, kecatat di audit."""
    entry = create_access_entry(registered_user, build_entry_dict(category_dict["Web"]))
    update_access_entry(registered_user, entry, build_entry_dict(category_dict["Web"], title="Portal HR Baru"))
    assert entry.title == "Portal HR Baru"
    assert count_entry_audit(AUDIT_ACTION_UPDATE) == 1


def test_update_by_other_user_denied(app, registered_user, other_user, category_dict):
    """Negative (security): data public orang lain ga bisa diubah user biasa."""
    entry = create_access_entry(other_user, build_entry_dict(category_dict["Web"], visibility=VISIBILITY_PUBLIC))
    with pytest.raises(PermissionDeniedError):
        update_access_entry(registered_user, entry, build_entry_dict(category_dict["Web"], title="Diubah"))


def test_admin_update_public_cannot_change_visibility(app, admin_user, other_user, category_dict):
    """Positive & negative: admin bisa edit data public, tapi ga bisa jadiin private."""
    entry = create_access_entry(other_user, build_entry_dict(category_dict["Web"], visibility=VISIBILITY_PUBLIC))
    update_access_entry(admin_user, entry, build_entry_dict(
        category_dict["Web"], title="Diubah Admin", visibility=VISIBILITY_PRIVATE,
    ))
    assert entry.title == "Diubah Admin"
    assert entry.visibility == VISIBILITY_PUBLIC


def test_delete_by_owner_removes_entry_and_fields(app, registered_user, category_dict):
    """Positive: data & field tambahannya kehapus, kecatat di audit."""
    entry = create_access_entry(
        registered_user, build_entry_dict(category_dict["General"]), [("A", "<p>1</p>"), ("B", "<p>2</p>")],
    )
    delete_access_entry(registered_user, entry)
    assert db.session.execute(db.select(db.func.count(AccessEntry.id))).scalar() == 0
    assert db.session.execute(db.select(db.func.count(AccessEntryField.id))).scalar() == 0
    assert count_entry_audit(AUDIT_ACTION_DELETE) == 1


# ambil data

def test_get_visible_entry_hides_private_of_other_user(app, registered_user, other_user, category_dict):
    """Negative (security): private orang lain ga bisa diambil lewat id."""
    private_entry = create_access_entry(other_user, build_entry_dict(category_dict["Web"], url="https://a.spindo.com"))
    public_entry = create_access_entry(other_user, build_entry_dict(
        category_dict["Web"], url="https://b.spindo.com", visibility=VISIBILITY_PUBLIC,
    ))
    assert get_visible_entry(registered_user, private_entry.id) is None
    assert get_visible_entry(registered_user, public_entry.id) is not None


def test_count_visible_entry_summary(app, registered_user, other_user, category_dict):
    """Positive: ringkasan cuma ngitung data yg boleh dilihat."""
    web = category_dict["Web"]
    create_access_entry(registered_user, build_entry_dict(web, url="https://1.spindo.com"))
    create_access_entry(registered_user, build_entry_dict(web, url="https://2.spindo.com", visibility=VISIBILITY_PUBLIC))
    create_access_entry(other_user, build_entry_dict(web, url="https://3.spindo.com", visibility=VISIBILITY_PUBLIC))
    create_access_entry(other_user, build_entry_dict(web, url="https://4.spindo.com"))
    summary_dict = count_visible_entry_summary(registered_user)
    assert summary_dict == {"total": 3, "public": 2, "private": 1}