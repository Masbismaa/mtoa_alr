"""Test backup & restore. pg_dump / pg_restore diganti palsu (test pake SQLite); jalur PostgreSQL beneran dicek manual."""
import json
import zipfile
from pathlib import Path

import pytest

from app.models import AuditLog
from app.services import backup_service
from app.utils.exceptions import ValidationError


@pytest.fixture()
def fake_pg(app, monkeypatch, tmp_path):
    """Backup folder sementara + pg_dump/pg_restore palsu. Return daftar perintah yg dipanggil."""
    app.config["BACKUP_FOLDER"] = str(tmp_path / "backups")
    call_list = []

    def fake_run_pg(tool, *arg_list):
        call_list.append(tool)
        if tool == "pg_dump":
            Path(arg_list[-1].removeprefix("--file=")).write_bytes(b"DUMP")

    monkeypatch.setattr(backup_service, "run_pg", fake_run_pg)
    monkeypatch.setattr(backup_service, "read_db_revision", lambda: "rev1")
    return call_list


def write_backup(app, name, manifest_dict, entry_dict):
    path = backup_service.get_backup_folder() / name
    with zipfile.ZipFile(path, "w") as zip_file:
        zip_file.writestr("manifest.json", json.dumps(manifest_dict))
        for entry, content in entry_dict.items():
            zip_file.writestr(entry, content)
    return path


def test_create_backup_contains_db_and_uploads(app, fake_pg):
    """Positive: zip isi manifest, dump, dan semua lampiran; muncul di daftar + audit."""
    (backup_service.get_upload_folder() / "a.png").write_bytes(b"PNG")
    backup_path = backup_service.create_backup()
    with zipfile.ZipFile(backup_path) as zip_file:
        assert sorted(zip_file.namelist()) == ["database.dump", "manifest.json", "uploads/a.png"]
        assert json.loads(zip_file.read("manifest.json"))["db_revision"] == "rev1"
    assert backup_service.list_backup() == [backup_path]
    assert AuditLog.query.filter_by(entity_type="backups", action="export").count() == 1


def test_restore_puts_back_missing_upload_and_keeps_safety_backup(app, fake_pg):
    """Positive: restore jalanin pg_restore, balikin lampiran yg hilang, dan backup keadaan sebelumnya dulu."""
    write_backup(app, "alr-backup-20260101-000000.zip", {"db_revision": "rev1", "created_at": "2026-01-01T00:00:00"},
                 {"database.dump": "DUMP", "uploads/a.png": "PNG"})
    safety_path = backup_service.restore_backup("alr-backup-20260101-000000.zip", "admin@spindo.com")
    assert fake_pg == ["pg_dump", "pg_restore"]
    assert (backup_service.get_upload_folder() / "a.png").read_bytes() == b"PNG"
    assert safety_path.is_file()
    restore_log = AuditLog.query.filter_by(entity_type="backups", action="import").one()
    assert restore_log.actor_email == "admin@spindo.com"
    assert restore_log.new_data == {"safety_backup": safety_path.name, "backup_created_at": "2026-01-01T00:00:00"}


@pytest.mark.parametrize("manifest_dict, entry_dict", [
    ({"db_revision": "rev0"}, {"database.dump": "DUMP"}),
    ({"db_revision": "rev1"}, {}),
    ({"db_revision": "rev1"}, {"database.dump": "DUMP", "uploads/../evil.py": "x"}),
    ({"db_revision": "rev1"}, {"database.dump": "DUMP", "uploads/sub/a.png": "x"}),
])
def test_restore_rejects_bad_backup_before_touching_db(app, fake_pg, manifest_dict, entry_dict):
    """Negative: beda versi migrasi, ga ada dump, atau path nyasar -> ditolak sebelum pg_restore."""
    write_backup(app, "alr-backup-20260101-000000.zip", manifest_dict, entry_dict)
    with pytest.raises(ValidationError):
        backup_service.restore_backup("alr-backup-20260101-000000.zip")
    assert fake_pg == []


@pytest.mark.parametrize("name", ["../secret.zip", "alr-backup-20260101-000000.zip", "other.zip"])
def test_get_backup_path_rejects_unknown_name(app, fake_pg, name):
    """Negative: nama ngasal / ../ / file yg ga ada -> ditolak."""
    with pytest.raises(ValidationError):
        backup_service.get_backup_path(name)


def test_backup_page_admin_only(client, logged_in_client, fake_pg):
    """Negative: user biasa ga bisa buka, unduh, atau restore."""
    assert logged_in_client.get("/backups/").status_code == 403
    assert logged_in_client.post("/backups/alr-backup-20260101-000000.zip/restore").status_code == 403


def test_admin_creates_and_downloads_backup(admin_client, fake_pg):
    """Positive: admin bikin backup lewat halaman, file muncul di daftar dan bisa diunduh."""
    response = admin_client.post("/backups/create", follow_redirects=True)
    name = backup_service.list_backup()[0].name
    assert name in response.get_data(as_text=True)
    download = admin_client.get(f"/backups/{name}/download")
    assert download.status_code == 200 and download.headers["Content-Disposition"].startswith("attachment")
    assert admin_client.get("/backups/alr-backup-20990101-000000.zip/download").status_code == 404
