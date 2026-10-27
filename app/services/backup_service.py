"""Backup & restore, dipisah 2 jenis di folder masing-masing (BACKUP_FOLDER/database & BACKUP_FOLDER/website):
- database: .zip isi manifest + dump PostgreSQL (pg_dump format custom)
- website: .zip isi manifest + semua lampiran (folder uploads)
ENCRYPTION_KEY sengaja ga ikut di file backup: simpen terpisah, tanpa kunci itu password di backup ga bisa dibaca."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from flask import current_app
from sqlalchemy.engine import make_url

from app.extensions import db
from app.services.attachment_service import get_upload_folder
from app.services.audit_service import log_audit
from app.utils.constants import AUDIT_ACTION_EXPORT, AUDIT_ACTION_IMPORT
from app.utils.datetime_helper import utc_now
from app.utils.exceptions import ValidationError, build_error

BACKUP_FIELD = "backup"
BACKUP_ENTITY = "backups"
BACKUP_KIND_DATABASE = "database"
BACKUP_KIND_WEBSITE = "website"
# jenis -> awalan nama file. Nama file = waktu UTC, jadi urut nama = urut waktu
BACKUP_PREFIX_DICT = {BACKUP_KIND_DATABASE: "alr-db", BACKUP_KIND_WEBSITE: "alr-web"}
BACKUP_NAME_PATTERN_DICT = {
    kind: re.compile(rf"^{prefix}-\d{{8}}-\d{{6}}\.zip$") for kind, prefix in BACKUP_PREFIX_DICT.items()
}
MANIFEST_NAME = "manifest.json"
DUMP_NAME = "database.dump"
UPLOAD_PREFIX = "uploads/"


def fail(message):
    raise ValidationError([build_error(BACKUP_FIELD, message)])


def read_backup_kind(name):
    """Jenis backup dari nama filenya (alr-db-... / alr-web-...), None kalau bukan file backup ALR."""
    return next((kind for kind, pattern in BACKUP_NAME_PATTERN_DICT.items() if pattern.match(name)), None)


def get_backup_folder(kind):
    """Folder file backup per jenis (di luar static, jadi cuma bisa diunduh lewat halaman admin)."""
    if kind not in BACKUP_PREFIX_DICT:
        fail("Unknown backup type")
    backup_folder = Path(current_app.config["BACKUP_FOLDER"]) / kind
    backup_folder.mkdir(parents=True, exist_ok=True)
    return backup_folder.resolve()


def list_backup(kind):
    """File backup satu jenis di server, terbaru dulu."""
    pattern = BACKUP_NAME_PATTERN_DICT[kind]
    return sorted(
        (path for path in get_backup_folder(kind).iterdir() if path.is_file() and pattern.match(path.name)),
        key=lambda path: path.name, reverse=True,
    )


def get_backup_path(kind, name):
    """Path backup dari jenis + namanya. Nama dicek pola dulu biar ga bisa nunjuk file lain (../ dsb)."""
    path = get_backup_folder(kind) / name
    if read_backup_kind(name) != kind or not path.is_file():
        fail("Backup file not found")
    return path


def read_db_url():
    url = make_url(current_app.config["SQLALCHEMY_DATABASE_URI"])
    if url.get_backend_name() != "postgresql":
        fail("Backup and restore only work on PostgreSQL")
    return url


def read_db_revision():
    """Versi migrasi database sekarang. Backup database cuma boleh di-restore ke versi yg sama persis."""
    read_db_url()
    return db.session.scalar(db.text("SELECT version_num FROM alembic_version"))


def run_pg(tool, *arg_list):
    """Jalanin pg_dump / pg_restore ke database app. Password lewat env, bukan argumen, biar ga keliatan di daftar proses."""
    url = read_db_url()
    executable = shutil.which(tool, path=current_app.config["PG_BIN_DIR"] or None)
    if not executable:
        fail(f"{tool} was not found on the server. Install the PostgreSQL client tools or set PG_BIN_DIR")
    env = dict(os.environ)
    env.update({key: str(value) for key, value in {
        "PGHOST": url.host, "PGPORT": url.port, "PGUSER": url.username, "PGPASSWORD": url.password,
    }.items() if value})
    result = subprocess.run([executable, *arg_list, f"--dbname={url.database}"], env=env, capture_output=True, text=True)
    if result.returncode != 0:
        current_app.logger.error("%s gagal: %s", tool, result.stderr)
        fail(f"{tool} failed. Check the server log for details")


def write_backup_file(kind, manifest_dict, write_content, user=None):
    """Bikin file backup baru di folder jenisnya, return path-nya. write_content(zip_file) ngisi isinya.
    Ditulis ke .part dulu: backup yg gagal di tengah ga pernah nongol di daftar."""
    name = f"{BACKUP_PREFIX_DICT[kind]}-{utc_now():%Y%m%d-%H%M%S}.zip"
    backup_path = get_backup_folder(kind) / name
    part_path = backup_path.with_name(name + ".part")
    try:
        # "x" = gagal kalau ada backup lain yg lagi dibikin di detik yg sama
        with zipfile.ZipFile(part_path, "x", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr(MANIFEST_NAME, json.dumps({"kind": kind, "created_at": utc_now().isoformat(), **manifest_dict}))
            write_content(zip_file)
        part_path.replace(backup_path)
    except FileExistsError:
        fail("Another backup is being created right now. Try again in a moment")
    finally:
        part_path.unlink(missing_ok=True)
    log_audit(AUDIT_ACTION_EXPORT, BACKUP_ENTITY, name, user=user, is_commit=True)
    return backup_path


def create_database_backup(user=None):
    """Backup database aja (dump PostgreSQL) ke BACKUP_FOLDER/database."""
    revision = read_db_revision()
    with tempfile.TemporaryDirectory() as temp_folder:
        dump_path = Path(temp_folder) / DUMP_NAME
        run_pg("pg_dump", "--format=custom", "--no-owner", "--no-privileges", f"--file={dump_path}")
        # dump custom udah kekompres, ga perlu dikompres lagi
        return write_backup_file(
            BACKUP_KIND_DATABASE, {"db_revision": revision},
            lambda zip_file: zip_file.write(dump_path, DUMP_NAME, compress_type=zipfile.ZIP_STORED), user,
        )


def create_website_backup(user=None):
    """Backup lampiran website aja (folder uploads) ke BACKUP_FOLDER/website."""
    def write_upload(zip_file):
        for path in sorted(get_upload_folder().iterdir()):
            if path.is_file() and not path.is_symlink():
                zip_file.write(path, UPLOAD_PREFIX + path.name)
    return write_backup_file(BACKUP_KIND_WEBSITE, {}, write_upload, user)


def read_backup_manifest(zip_file, kind):
    """Isi manifest, sekalian mastiin file ini beneran backup ALR jenis yg diminta."""
    try:
        manifest = json.loads(zip_file.read(MANIFEST_NAME))
    except (KeyError, ValueError):
        fail("This file is not an ALR backup")
    if manifest.get("kind") != kind:
        fail(f"This file is not an ALR {kind} backup")
    return manifest


def restore_database_backup(name, actor_email=None):
    """Timpa database dari backup. Sebelumnya otomatis bikin backup database keadaan sekarang
    (return path-nya), jadi restore yg salah pilih masih bisa dibalikin."""
    backup_path = get_backup_path(BACKUP_KIND_DATABASE, name)
    with zipfile.ZipFile(backup_path) as zip_file:
        manifest = read_backup_manifest(zip_file, BACKUP_KIND_DATABASE)
        try:
            zip_file.getinfo(DUMP_NAME)
        except KeyError:
            fail("This file is not an ALR backup")
        current_revision = read_db_revision()
        if manifest.get("db_revision") != current_revision:
            fail(f"This backup is for database version {manifest.get('db_revision')}, but the app is on {current_revision}. "
                 "Restore it with the matching app version, then run the migrations")

        safety_backup_path = create_database_backup()
        # lepas koneksi request ini dulu: lock baca-nya bikin DROP TABLE di pg_restore nunggu selamanya
        db.session.remove()
        with tempfile.TemporaryDirectory() as temp_folder:
            dump_path = zip_file.extract(DUMP_NAME, temp_folder)
            # satu transaksi: gagal di tengah = database balik utuh ke keadaan sebelum restore
            run_pg("pg_restore", "--clean", "--if-exists", "--single-transaction", "--exit-on-error",
                   "--no-owner", "--no-privileges", dump_path)

    # user_id sengaja kosong: akun yg nge-restore belum tentu ada di database hasil restore.
    # audit log ikut balik ke isi backup, jadi catatan sesudah backup_created_at (termasuk pembuatan backup ini &
    # backup pengamannya) cuma ada di safety_backup
    log_audit(AUDIT_ACTION_IMPORT, BACKUP_ENTITY, name, new_data_dict={
        "safety_backup": safety_backup_path.name, "backup_created_at": manifest.get("created_at"),
    }, actor_email=actor_email, is_commit=True)
    return safety_backup_path


def restore_website_backup(name, actor_email=None):
    """Balikin lampiran dari backup: cuma nambahin file yg belum ada, file yg udah ada ga ditimpa / dihapus.
    Return jumlah file yg dibalikin."""
    backup_path = get_backup_path(BACKUP_KIND_WEBSITE, name)
    with zipfile.ZipFile(backup_path) as zip_file:
        read_backup_manifest(zip_file, BACKUP_KIND_WEBSITE)
        upload_name_list = [entry for entry in zip_file.namelist() if entry.startswith(UPLOAD_PREFIX)]
        for entry in upload_name_list:
            file_name = entry[len(UPLOAD_PREFIX):]
            # lampiran cuma boleh file langsung di folder uploads, ga boleh nyasar keluar (../, subfolder, C:)
            if not file_name or file_name.startswith(".") or "\\" in file_name or Path(file_name).name != file_name:
                fail("The backup file contains an invalid path")

        # nama file lampiran unik (acak), jadi file yg udah ada pasti isinya sama: cukup tambahin yg belum ada.
        # file yg ga dirujuk database lagi dibersihin lewat "flask cleanup-attachments"
        upload_folder = get_upload_folder()
        restored_count = 0
        for entry in upload_name_list:
            target_path = upload_folder / entry[len(UPLOAD_PREFIX):]
            if not target_path.exists():
                with zip_file.open(entry) as source_file, open(target_path, "xb") as target_file:
                    shutil.copyfileobj(source_file, target_file)
                restored_count += 1

    log_audit(AUDIT_ACTION_IMPORT, BACKUP_ENTITY, name, new_data_dict={"restored_file_count": restored_count},
              actor_email=actor_email, is_commit=True)
    return restored_count
