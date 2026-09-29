"""Urusan lampiran: validasi upload, simpen ke disk, hapus, ambil buat download."""

import uuid
from pathlib import Path

from flask import current_app

from app.extensions import db
from app.models import AccessEntry, Attachment
from app.security.access_policy import build_visible_entry_filter
from app.security.file_validator import clean_display_filename, detect_content_type
from app.utils.constants import ATTACHMENT_MAX_COUNT, ATTACHMENT_MAX_SIZE_BYTES
from app.utils.exceptions import build_error

ATTACHMENT_FIELD = "attachments"


def get_upload_folder():
    """Folder lampiran, dibikin otomatis kalau belum ada."""
    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    upload_folder.mkdir(parents=True, exist_ok=True)
    return upload_folder.resolve()


def get_stored_file_path(stored_filename):
    """Path lengkap file di disk. Dicek biar ga bisa keluar dari folder uploads."""
    upload_folder = get_upload_folder()
    file_path = (upload_folder / stored_filename).resolve()
    if file_path.parent != upload_folder:
        raise ValueError("Path file tidak valid")
    return file_path


def prepare_upload_list(file_storage_list, existing_count=0):
    """Validasi semua file upload. Return (prepared_list, error_list). Belum ada yg ditulis ke disk."""
    # input file kosong (ga milih apa-apa) dilewatin
    upload_list = [file_storage for file_storage in (file_storage_list or []) if file_storage and file_storage.filename]
    if not upload_list:
        return [], []

    if existing_count + len(upload_list) > ATTACHMENT_MAX_COUNT:
        return [], [build_error(
            ATTACHMENT_FIELD,
            f"Maksimal {ATTACHMENT_MAX_COUNT} lampiran per data (yang sudah ada: {existing_count})",
        )]

    prepared_list = []
    error_list = []
    for file_storage in upload_list:
        display_name = clean_display_filename(file_storage.filename)
        # baca maksimal batas + 1 byte, cukup buat tau kegedean atau nggak
        content_bytes = file_storage.stream.read(ATTACHMENT_MAX_SIZE_BYTES + 1)

        if len(content_bytes) > ATTACHMENT_MAX_SIZE_BYTES:
            max_size_mb = ATTACHMENT_MAX_SIZE_BYTES // (1024 * 1024)
            error_list.append(build_error(ATTACHMENT_FIELD, f"{display_name}: lebih dari {max_size_mb}MB"))
            continue

        try:
            extension, content_type = detect_content_type(display_name, content_bytes)
        except ValueError as error:
            error_list.append(build_error(ATTACHMENT_FIELD, f"{display_name}: {error}"))
            continue

        prepared_list.append({
            "original_filename": display_name,
            "extension": extension,
            "content_type": content_type,
            "content_bytes": content_bytes,
        })
    return prepared_list, error_list


def store_prepared_attachment_list(entry, user, prepared_list):
    """Tulis file ke disk (nama diacak) + tambahin ke entry. Return list path yg udah ketulis."""
    upload_folder = get_upload_folder()
    written_path_list = []
    try:
        for prepared_dict in prepared_list:
            stored_filename = f"{uuid.uuid4().hex}.{prepared_dict['extension']}"
            file_path = upload_folder / stored_filename
            file_path.write_bytes(prepared_dict["content_bytes"])
            written_path_list.append(file_path)

            entry.attachment_list.append(Attachment(
                user_id=user.id,
                original_filename=prepared_dict["original_filename"],
                stored_filename=stored_filename,
                content_type=prepared_dict["content_type"],
                file_size=len(prepared_dict["content_bytes"]),
            ))
    except OSError:
        # gagal di tengah jalan -> yg udah ketulis dihapus lagi
        remove_file_path_list(written_path_list)
        raise
    return written_path_list

def remove_file_path_list(file_path_list):
    """Hapus file dari disk (yg udah ga ada dibiarin)."""
    for file_path in file_path_list:
        Path(file_path).unlink(missing_ok=True)

def remove_stored_file_list(stored_filename_list):
    """Hapus file lampiran berdasarkan nama di disk."""
    remove_file_path_list([get_stored_file_path(stored_filename) for stored_filename in stored_filename_list])

def pick_entry_attachment_list(entry, raw_id_list):
    """Ambil lampiran yg mau dihapus, TAPI cuma yg emang punya entry ini (anti IDOR)."""
    id_set = set()
    for raw_id in raw_id_list or []:
        try:
            id_set.add(int(raw_id))
        except (TypeError, ValueError):
            continue
    return [attachment for attachment in entry.attachment_list if attachment.id in id_set]

def get_visible_attachment(user, attachment_id):
    """Ambil lampiran kalau user boleh liat data induknya. None kalau nggak."""
    return db.session.execute(
        db.select(Attachment)
        .join(AccessEntry, Attachment.access_entry_id == AccessEntry.id)
        .where(Attachment.id == attachment_id, build_visible_entry_filter(user))
    ).scalar_one_or_none()