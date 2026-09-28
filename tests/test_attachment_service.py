"""Test lampiran lewat service: simpan, batas, hapus, hak akses."""
from pathlib import Path

import pytest

from app.extensions import db
from app.models import AccessEntry, Attachment
from app.services import attachment_service
from app.services.access_entry_service import create_access_entry, delete_access_entry, update_access_entry
from app.services.attachment_service import get_stored_file_path, get_visible_attachment
from app.utils.constants import VISIBILITY_PRIVATE, VISIBILITY_PUBLIC
from app.utils.exceptions import ValidationError


def build_entry_dict(category, **override_dict):
    """Helper: data link contoh."""
    entry_dict = {
        "category_id": category.id, "title": "Router Lantai 2", "url": "https://router.spindo.com",
        "address": "", "port": "", "username": "", "access_note": "", "description": "",
        "visibility": VISIBILITY_PRIVATE,
    }
    entry_dict.update(override_dict)
    return entry_dict

def count_stored_file(app):
    """Helper: jumlah file di folder upload."""
    upload_folder = Path(app.config["UPLOAD_FOLDER"])
    return len(list(upload_folder.glob("*"))) if upload_folder.exists() else 0

def test_create_entry_with_attachments_stores_files(app, registered_user, category_dict, sample_file_dict, make_file_storage):
    """Positive: file kesimpen dgn nama acak, info-nya kecatat."""
    upload_list = [
        make_file_storage(sample_file_dict["png"], "foto router.png"),
        make_file_storage(sample_file_dict["pdf"], "manual.pdf"),
    ]
    entry = create_access_entry(registered_user, build_entry_dict(category_dict["Web"]), upload_file_list=upload_list)

    assert [attachment.original_filename for attachment in entry.attachment_list] == ["foto router.png", "manual.pdf"]
    first_attachment = entry.attachment_list[0]
    assert first_attachment.stored_filename != "foto router.png"
    assert first_attachment.stored_filename.endswith(".png")
    assert first_attachment.content_type == "image/png"
    assert first_attachment.created_at is not None
    assert get_stored_file_path(first_attachment.stored_filename).read_bytes() == sample_file_dict["png"]

def test_upload_more_than_max_count_rejected(app, registered_user, category_dict, sample_file_dict, make_file_storage):
    """Negative: lebih dari 5 file ditolak, data ga kesimpen."""
    upload_list = [make_file_storage(sample_file_dict["png"], f"foto{index}.png") for index in range(6)]
    with pytest.raises(ValidationError):
        create_access_entry(registered_user, build_entry_dict(category_dict["Web"]), upload_file_list=upload_list)
    assert db.session.execute(db.select(db.func.count(AccessEntry.id))).scalar() == 0

def test_upload_too_large_rejected(app, registered_user, category_dict, sample_file_dict, make_file_storage, monkeypatch):
    """Negative: file kegedean ditolak (batasnya dikecilin biar test cepet)."""
    monkeypatch.setattr(attachment_service, "ATTACHMENT_MAX_SIZE_BYTES", 10)
    with pytest.raises(ValidationError):
        create_access_entry(
            registered_user, build_entry_dict(category_dict["Web"]),
            upload_file_list=[make_file_storage(sample_file_dict["png"], "besar.png")],
        )

def test_invalid_file_not_written_to_disk(app, registered_user, category_dict, sample_file_dict, make_file_storage):
    """Negative (security): file palsu ditolak & ga ada yg ketulis ke disk."""
    with pytest.raises(ValidationError):
        create_access_entry(
            registered_user, build_entry_dict(category_dict["Web"]),
            upload_file_list=[make_file_storage(sample_file_dict["exe"], "invoice.pdf")],
        )
    assert count_stored_file(app) == 0

def test_update_delete_and_add_attachment(app, registered_user, category_dict, sample_file_dict, make_file_storage):
    """Positive: lampiran lama dihapus (file ikut ilang), lampiran baru masuk."""
    entry = create_access_entry(
        registered_user, build_entry_dict(category_dict["Web"]),
        upload_file_list=[make_file_storage(sample_file_dict["png"], "lama.png")],
    )
    old_attachment = entry.attachment_list[0]
    old_file_path = get_stored_file_path(old_attachment.stored_filename)

    update_access_entry(
        registered_user, entry, build_entry_dict(category_dict["Web"]),
        upload_file_list=[make_file_storage(sample_file_dict["pdf"], "baru.pdf")],
        delete_attachment_id_list=[str(old_attachment.id)],
    )
    assert [attachment.original_filename for attachment in entry.attachment_list] == ["baru.pdf"]
    assert not old_file_path.exists()

def test_update_count_limit_includes_existing(app, registered_user, category_dict, sample_file_dict, make_file_storage):
    """Negative: udah ada 4 lampiran, nambah 2 lagi -> kelebihan."""
    entry = create_access_entry(
        registered_user, build_entry_dict(category_dict["Web"]),
        upload_file_list=[make_file_storage(sample_file_dict["png"], f"lama{index}.png") for index in range(4)],
    )
    with pytest.raises(ValidationError):
        update_access_entry(
            registered_user, entry, build_entry_dict(category_dict["Web"]),
            upload_file_list=[make_file_storage(sample_file_dict["pdf"], f"baru{index}.pdf") for index in range(2)],
        )

def test_delete_entry_removes_files(app, registered_user, category_dict, sample_file_dict, make_file_storage):
    """Positive: hapus data link -> file lampirannya ikut kehapus dari disk."""
    entry = create_access_entry(
        registered_user, build_entry_dict(category_dict["Web"]),
        upload_file_list=[make_file_storage(sample_file_dict["png"], "foto.png")],
    )
    file_path = get_stored_file_path(entry.attachment_list[0].stored_filename)
    delete_access_entry(registered_user, entry)
    assert not file_path.exists()
    assert db.session.execute(db.select(db.func.count(Attachment.id))).scalar() == 0

def test_cannot_delete_attachment_of_other_entry(app, registered_user, other_user, category_dict, sample_file_dict, make_file_storage):
    """Negative (security/IDOR): id lampiran data orang lain diselipin -> dicuekin."""
    other_entry = create_access_entry(
        other_user, build_entry_dict(category_dict["Web"], url="https://lain.spindo.com"),
        upload_file_list=[make_file_storage(sample_file_dict["png"], "punya_orang.png")],
    )
    other_attachment_id = other_entry.attachment_list[0].id
    my_entry = create_access_entry(registered_user, build_entry_dict(category_dict["Web"]))

    update_access_entry(
        registered_user, my_entry, build_entry_dict(category_dict["Web"]),
        delete_attachment_id_list=[str(other_attachment_id)],
    )
    assert db.session.get(Attachment, other_attachment_id) is not None

def test_get_visible_attachment_hides_private_of_other_user(app, registered_user, other_user, category_dict, sample_file_dict, make_file_storage):
    """Negative (security): lampiran di data private orang lain ga bisa diambil."""
    private_entry = create_access_entry(
        other_user, build_entry_dict(category_dict["Web"], url="https://a.spindo.com"),
        upload_file_list=[make_file_storage(sample_file_dict["png"], "a.png")],
    )
    public_entry = create_access_entry(
        other_user, build_entry_dict(category_dict["Web"], url="https://b.spindo.com", visibility=VISIBILITY_PUBLIC),
        upload_file_list=[make_file_storage(sample_file_dict["png"], "b.png")],
    )
    assert get_visible_attachment(registered_user, private_entry.attachment_list[0].id) is None
    assert get_visible_attachment(registered_user, public_entry.attachment_list[0].id) is not None