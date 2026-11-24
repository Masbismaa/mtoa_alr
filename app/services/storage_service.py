"""Folder simpan lampiran & backup: default dari .env, bisa dipindah Admin lewat menu Manage."""
import os
import shutil
from pathlib import Path

from flask import current_app

from app.extensions import db
from app.models import AppSetting
from app.services.audit_service import log_audit
from app.utils.constants import AUDIT_ACTION_UPDATE
from app.utils.exceptions import ValidationError, build_error

STORAGE_ENTITY = "storage"
# key pengaturan = nama config .env-nya
STORAGE_NAME_LIST = ("UPLOAD_FOLDER", "BACKUP_FOLDER")


def fail(name, message):
    raise ValidationError([build_error(name, message)])


def get_storage_folder(name):
    """Folder yg dipake sekarang (database dulu, kalau belum pernah dipindah dari .env), dibikin kalau belum ada."""
    value = db.session.scalar(db.select(AppSetting.value).where(AppSetting.key == name))
    folder = Path(value or current_app.config[name])
    folder.mkdir(parents=True, exist_ok=True)
    return folder.resolve()


def is_inside(path, folder):
    return path == folder or folder in path.parents


def validate_new_folder(name, path_text):
    """Folder tujuan harus path absolut, kosong, bisa ditulis, dan ga numpuk sama folder lain / folder web."""
    path_text = (path_text or "").strip()
    if not path_text or not os.path.isabs(path_text):
        fail(name, "Enter a full folder path, for example /data/alr/uploads")
    new_folder = Path(path_text).resolve()
    old_folder = get_storage_folder(name)
    if new_folder == old_folder:
        fail(name, "This is already the current folder")
    if is_inside(new_folder, old_folder) or is_inside(old_folder, new_folder):
        fail(name, "The new folder cannot be inside the current folder, or the other way around")
    other_folder = get_storage_folder(next(other for other in STORAGE_NAME_LIST if other != name))
    if is_inside(new_folder, other_folder) or is_inside(other_folder, new_folder):
        fail(name, "The attachment and backup folders must be separate")
    # folder aplikasi (termasuk static) bisa kebaca lewat web / ketimpa deploy
    if is_inside(new_folder, Path(current_app.root_path).resolve()):
        fail(name, "The folder cannot be inside the application code")
    try:
        new_folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        fail(name, "The folder cannot be created. Check the server folder permissions")
    if not new_folder.is_dir() or any(new_folder.iterdir()):
        fail(name, "The new folder must be empty")
    if not os.access(new_folder, os.W_OK):
        fail(name, "The app cannot write to this folder. Check the server folder permissions")
    return old_folder, new_folder


def list_child_folder(path_text):
    """Subfolder langsung dari path di server buat tombol Browse (nama folder aja, file ga ikut)."""
    if not path_text or not os.path.isabs(path_text):
        fail("path", "Enter a full folder path")
    folder = Path(path_text).resolve()
    try:
        child_list = sorted((child.name for child in folder.iterdir() if child.is_dir()), key=str.lower)
    except OSError:
        fail("path", "This folder cannot be opened")
    return {"path": str(folder), "parent": str(folder.parent), "folder_list": child_list}


def remove_path(path):
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def move_storage_folder(name, path_text, user=None):
    """Salin semua isi folder lama ke folder baru, simpen pengaturan, baru hapus yg lama. Return jumlah item."""
    if name not in STORAGE_NAME_LIST:
        fail("storage", "Unknown folder")
    old_folder, new_folder = validate_new_folder(name, path_text)
    # shortcut: file yg masuk ke folder lama selama proses salin ketinggalan di sana; kalau datanya udah gede, pindahin pas ga ada yg pake
    entry_list = list(old_folder.iterdir())
    try:
        for entry in entry_list:
            if entry.is_dir():
                shutil.copytree(entry, new_folder / entry.name)
            else:
                shutil.copy2(entry, new_folder / entry.name)
    except OSError:
        current_app.logger.exception("Gagal nyalin %s ke %s", old_folder, new_folder)
        for entry in new_folder.iterdir():
            remove_path(entry)
        fail(name, "Copying the files failed (disk full or no permission?). Nothing was moved")

    setting = db.session.get(AppSetting, name) or AppSetting(key=name)
    setting.value = str(new_folder)
    db.session.add(setting)
    log_audit(AUDIT_ACTION_UPDATE, STORAGE_ENTITY, name, old_data_dict={"path": str(old_folder)},
              new_data_dict={"path": str(new_folder), "moved_count": len(entry_list)}, user=user, is_commit=True)

    # pengaturan udah kesimpen, jadi gagal hapus di sini cuma ninggalin salinan lama, ga ada data ilang
    for entry in entry_list:
        try:
            remove_path(entry)
        except OSError:
            current_app.logger.warning("Salinan lama ga bisa dihapus: %s", entry)
    return len(entry_list)
