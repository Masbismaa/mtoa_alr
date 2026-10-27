"""Test backup & restore (database & website dipisah). pg_dump / pg_restore diganti palsu (test pake SQLite);
jalur PostgreSQL beneran dicek manual."""
import json
import zipfile
from pathlib import Path

import pytest

from app.models import AuditLog
from app.services import backup_service
from app.utils.exceptions import ValidationError

DB_NAME = "alr-db-20260101-000000.zip"
WEB_NAME = "alr-web-20260101-000000.zip"


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


def write_backup(kind, name, manifest_dict, entry_dict):
    path = backup_service.get_backup_folder(kind) / name
    with zipfile.ZipFile(path, "w") as zip_file:
        zip_file.writestr("manifest.json", json.dumps(manifest_dict))
        for entry, content in entry_dict.items():
            zip_file.writestr(entry, content)
    return path


def test_database_and_website_backup_go_to_separate_folders(app, fake_pg):
    """Positive: backup database cuma isi dump, backup website cuma isi lampiran, foldernya beda; audit kecatet."""
    (backup_service.get_upload_folder() / "a.png").write_bytes(b"PNG")
    db_path = backup_service.create_database_backup()
    web_path = backup_service.create_website_backup()
    assert db_path.parent.name == "database" and web_path.parent.name == "website"
    with zipfile.ZipFile(db_path) as zip_file:
        assert sorted(zip_file.namelist()) == ["database.dump", "manifest.json"]
        assert json.loads(zip_file.read("manifest.json"))["db_revision"] == "rev1"
    with zipfile.ZipFile(web_path) as zip_file:
        assert sorted(zip_file.namelist()) == ["manifest.json", "uploads/a.png"]
    assert backup_service.list_backup("database") == [db_path]
    assert backup_service.list_backup("website") == [web_path]
    # backup website ga butuh pg_dump
    assert fake_pg == ["pg_dump"]
    assert AuditLog.query.filter_by(entity_type="backups", action="export").count() == 2


def test_restore_database_keeps_safety_backup(app, fake_pg):
    """Positive: restore database jalanin pg_restore, dan backup database keadaan sebelumnya dulu."""
    write_backup("database", DB_NAME, {"kind": "database", "db_revision": "rev1", "created_at": "2026-01-01T00:00:00"},
                 {"database.dump": "DUMP"})
    safety_path = backup_service.restore_database_backup(DB_NAME, "admin@spindo.com")
    assert fake_pg == ["pg_dump", "pg_restore"]
    assert safety_path.is_file() and safety_path.parent.name == "database"
    restore_log = AuditLog.query.filter_by(entity_type="backups", action="import").one()
    assert restore_log.actor_email == "admin@spindo.com"
    assert restore_log.new_data == {"safety_backup": safety_path.name, "backup_created_at": "2026-01-01T00:00:00"}


def test_restore_website_adds_only_missing_upload(app, fake_pg):
    """Positive: restore website cuma nambahin lampiran yg hilang, file yg udah ada ga ditimpa, database ga disentuh."""
    upload_folder = backup_service.get_upload_folder()
    (upload_folder / "b.png").write_bytes(b"KEEP")
    write_backup("website", WEB_NAME, {"kind": "website"}, {"uploads/a.png": "PNG", "uploads/b.png": "OTHER"})
    assert backup_service.restore_website_backup(WEB_NAME, "admin@spindo.com") == 1
    assert (upload_folder / "a.png").read_bytes() == b"PNG"
    assert (upload_folder / "b.png").read_bytes() == b"KEEP"
    assert fake_pg == []


@pytest.mark.parametrize("manifest_dict, entry_dict", [
    ({"kind": "database", "db_revision": "rev0"}, {"database.dump": "DUMP"}),
    ({"kind": "database", "db_revision": "rev1"}, {}),
    # file website yg diganti nama jadi alr-db-... tetep ditolak
    ({"kind": "website"}, {"database.dump": "DUMP"}),
    ({"db_revision": "rev1"}, {"database.dump": "DUMP"}),
])
def test_restore_database_rejects_bad_backup_before_touching_db(app, fake_pg, manifest_dict, entry_dict):
    """Negative: beda versi migrasi, ga ada dump, atau bukan backup database -> ditolak sebelum pg_restore."""
    write_backup("database", DB_NAME, manifest_dict, entry_dict)
    with pytest.raises(ValidationError):
        backup_service.restore_database_backup(DB_NAME)
    assert fake_pg == []


@pytest.mark.parametrize("manifest_dict, entry_dict", [
    ({"kind": "website"}, {"uploads/../evil.py": "x"}),
    ({"kind": "website"}, {"uploads/sub/a.png": "x"}),
    ({"kind": "database"}, {"uploads/a.png": "x"}),
])
def test_restore_website_rejects_bad_backup(app, fake_pg, manifest_dict, entry_dict):
    """Negative: path nyasar keluar folder uploads atau bukan backup website -> ditolak, ga ada file ditulis."""
    write_backup("website", WEB_NAME, manifest_dict, entry_dict)
    with pytest.raises(ValidationError):
        backup_service.restore_website_backup(WEB_NAME)
    assert list(backup_service.get_upload_folder().iterdir()) == []


@pytest.mark.parametrize("kind, name", [
    ("database", "../secret.zip"), ("database", DB_NAME), ("database", "other.zip"),
    # nama backup website ga boleh dibuka lewat jenis database (dan sebaliknya)
    ("database", WEB_NAME), ("website", DB_NAME), ("other", DB_NAME),
])
def test_get_backup_path_rejects_unknown_name(app, fake_pg, kind, name):
    """Negative: nama ngasal / ../ / file yg ga ada / jenis ga cocok -> ditolak."""
    write_backup("website", WEB_NAME, {"kind": "website"}, {})
    with pytest.raises(ValidationError):
        backup_service.get_backup_path(kind, name)


def test_backup_page_admin_only(client, logged_in_client, fake_pg):
    """Negative: user biasa ga bisa buka, bikin, atau restore."""
    assert logged_in_client.get("/backups/").status_code == 403
    assert logged_in_client.post("/backups/database/create").status_code == 403
    assert logged_in_client.post(f"/backups/database/{DB_NAME}/restore").status_code == 403


def test_admin_creates_downloads_and_restores_per_kind(admin_client, fake_pg):
    """Positive: admin bikin backup tiap jenis lewat halaman, muncul di kartunya, bisa diunduh & di-restore."""
    for kind in ("database", "website"):
        response = admin_client.post(f"/backups/{kind}/create", follow_redirects=True)
        name = backup_service.list_backup(kind)[0].name
        assert name in response.get_data(as_text=True)
        download = admin_client.get(f"/backups/{kind}/{name}/download")
        assert download.status_code == 200 and download.headers["Content-Disposition"].startswith("attachment")
    web_name = backup_service.list_backup("website")[0].name
    response = admin_client.post(f"/backups/website/{web_name}/restore", follow_redirects=True)
    assert "Attachments restored from" in response.get_data(as_text=True)
    # jenis ngasal / nama ga ada / jenis ga cocok sama namanya -> 404
    assert admin_client.post("/backups/other/create").status_code == 404
    assert admin_client.get(f"/backups/database/{DB_NAME}/download").status_code == 404
    assert admin_client.get(f"/backups/database/{web_name}/download").status_code == 404


def test_cli_backup_creates_both_kinds_and_restore_detects_kind(app, fake_pg, tmp_path):
    """Positive + negative: "flask backup" bikin dua-duanya (--only satu), "flask restore" milih jenis dari nama file."""
    runner = app.test_cli_runner()
    assert runner.invoke(args=["backup"]).exit_code == 0
    assert len(backup_service.list_backup("database")) == 1 and len(backup_service.list_backup("website")) == 1
    fake_pg.clear()
    assert runner.invoke(args=["backup", "--only", "website"]).exit_code == 0
    # --only website ga nyentuh database sama sekali
    assert fake_pg == []
    # file dari luar folder backup disalin ke folder jenisnya dulu
    outside_path = tmp_path / "alr-web-20250101-000000.zip"
    with zipfile.ZipFile(outside_path, "w") as zip_file:
        zip_file.writestr("manifest.json", json.dumps({"kind": "website"}))
        zip_file.writestr("uploads/c.png", "PNG")
    result = runner.invoke(args=["restore", str(outside_path), "--yes"])
    assert result.exit_code == 0, result.output
    assert (backup_service.get_upload_folder() / "c.png").is_file()
    assert (backup_service.get_backup_folder("website") / outside_path.name).is_file()
    other_path = tmp_path / "random.zip"
    other_path.write_bytes(b"x")
    assert runner.invoke(args=["restore", str(other_path), "--yes"]).exit_code != 0
