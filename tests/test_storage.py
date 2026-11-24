"""Test menu Manage: pindah folder lampiran & backup."""
import pytest

from app.models import AuditLog
from app.services.attachment_service import get_upload_folder
from app.services.backup_service import get_backup_folder
from app.services.storage_service import move_storage_folder
from app.utils.exceptions import ValidationError


def test_move_upload_folder_copies_files_then_switches(app, tmp_path):
    """Positive: isi folder lama pindah semua, helper lampiran langsung nunjuk folder baru, audit kecatet."""
    (get_upload_folder() / "a.png").write_bytes(b"PNG")
    old_folder = get_upload_folder()
    assert move_storage_folder("UPLOAD_FOLDER", str(tmp_path / "new_uploads")) == 1
    assert get_upload_folder() == (tmp_path / "new_uploads").resolve()
    assert (get_upload_folder() / "a.png").read_bytes() == b"PNG"
    assert list(old_folder.iterdir()) == []
    assert AuditLog.query.filter_by(entity_type="storage", entity_id="UPLOAD_FOLDER").count() == 1


def test_move_backup_folder_keeps_subfolders(app, tmp_path):
    """Positive: subfolder database/website ikut pindah, jadi backup lama tetap kebaca."""
    (get_backup_folder("database") / "alr-db-20260101-000000.zip").write_bytes(b"ZIP")
    move_storage_folder("BACKUP_FOLDER", str(tmp_path / "new_backups"))
    assert (get_backup_folder("database") / "alr-db-20260101-000000.zip").read_bytes() == b"ZIP"
    assert get_backup_folder("database").parent == (tmp_path / "new_backups").resolve()


@pytest.mark.parametrize("make_path", [
    lambda tmp_path, app: "relative/folder",
    lambda tmp_path, app: "",
    lambda tmp_path, app: str(tmp_path / "uploads" / "inside"),
    lambda tmp_path, app: str(tmp_path / "backups" / "uploads"),
    lambda tmp_path, app: app.static_folder + "/uploads",
])
def test_move_rejects_bad_target(app, tmp_path, make_path):
    """Negative: path relatif / kosong / numpuk folder lain / di dalam folder aplikasi ditolak."""
    with pytest.raises(ValidationError):
        move_storage_folder("UPLOAD_FOLDER", make_path(tmp_path, app))
    assert get_upload_folder() == (tmp_path / "uploads").resolve()


def test_move_rejects_non_empty_target(app, tmp_path):
    """Negative: folder tujuan yg udah ada isinya ditolak biar ga ketimpa."""
    (tmp_path / "full").mkdir()
    (tmp_path / "full" / "x.txt").write_text("x")
    with pytest.raises(ValidationError):
        move_storage_folder("UPLOAD_FOLDER", str(tmp_path / "full"))


def test_manage_page_admin_only(logged_in_client, tmp_path):
    """Negative (RBAC): user biasa ga bisa buka atau mindahin folder."""
    assert logged_in_client.get("/manage/").status_code == 403
    assert logged_in_client.post("/manage/UPLOAD_FOLDER/move", data={"path": str(tmp_path / "x")}).status_code == 403


def test_admin_moves_folder_from_page(admin_client, tmp_path):
    """Positive: admin bisa buka halaman & mindahin folder."""
    assert admin_client.get("/manage/").status_code == 200
    assert admin_client.post("/manage/OTHER/move").status_code == 404
    response = admin_client.post("/manage/UPLOAD_FOLDER/move", data={"path": str(tmp_path / "x")}, follow_redirects=True)
    assert b"Folder moved" in response.data

