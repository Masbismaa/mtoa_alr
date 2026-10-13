"""Test integrasi PostgreSQL beneran: kunci baris (FOR UPDATE), index unik, & trigger audit log.

Test lain pakai SQLite di memori, yg ga punya FOR UPDATE & ga ngejalanin migrasi, jadi balapan request
barengan ga kebukti di sana. File ini cuma jalan kalau TEST_POSTGRES_URL diisi (job CI postgres_test),
ke database yg skemanya udah dibikin lewat `flask db upgrade` (bukan create_all), biar migrasinya ikut keuji.
Data test ga dihapus (audit log emang ga bisa dihapus), jadi pakai database khusus test yg dibuang abis CI.
"""
import io
import os
import threading
import time
import uuid

import pytest
from werkzeug.datastructures import FileStorage

TEST_POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not TEST_POSTGRES_URL, reason="TEST_POSTGRES_URL kosong (cuma jalan di job CI postgres_test)")

from app import create_app  # noqa: E402
from app.config import TestingConfig  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import AccessEntry, Attachment, AuditLog, Category  # noqa: E402
from app.services import attachment_service, category_service  # noqa: E402
from app.services.access_entry_service import create_access_entry, update_access_entry  # noqa: E402
from app.services.auth_service import register_user  # noqa: E402
from app.services.seed_service import seed_default_categories  # noqa: E402
from app.utils.constants import VISIBILITY_PRIVATE  # noqa: E402
from app.utils.exceptions import ValidationError  # noqa: E402

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20


@pytest.fixture()
def pg_app(monkeypatch, tmp_path):
    monkeypatch.setattr(TestingConfig, "SQLALCHEMY_DATABASE_URI", TEST_POSTGRES_URL)
    app = create_app("testing")
    app.config["UPLOAD_FOLDER"] = str(tmp_path / "uploads")
    with app.app_context():
        seed_default_categories()
    return app


def run_together(app, callback_list):
    """Jalanin beberapa fungsi di thread terpisah (tiap thread punya koneksi DB sendiri), mulai barengan.
    Return list ("ok", hasil) / ("error", exception) sesuai urutan callback."""
    barrier = threading.Barrier(len(callback_list))
    result_list = [None] * len(callback_list)

    def worker(index, callback):
        with app.app_context():
            try:
                barrier.wait()
                result_list[index] = ("ok", callback())
            except Exception as error:  # noqa: BLE001
                result_list[index] = ("error", error)
            finally:
                db.session.remove()

    thread_list = [threading.Thread(target=worker, args=(index, callback)) for index, callback in enumerate(callback_list)]
    for thread in thread_list:
        thread.start()
    for thread in thread_list:
        thread.join(30)
    return result_list


def build_entry_dict(category_id):
    """Data link kategori Web (URL wajib), unik tiap dipanggil biar ga dianggap data dobel antar run."""
    token = uuid.uuid4().hex[:8]
    return {"category_id": category_id, "title": f"Portal {token}", "url": f"https://{token}.spindo.com", "address": "",
            "port": "", "username": "", "access_note": "", "description": "", "visibility": VISIBILITY_PRIVATE}


def test_concurrent_uploads_cannot_exceed_entry_limit(pg_app, monkeypatch):
    """Negative: 2 upload barengan ke link yg udah punya 4 lampiran, dua-duanya sempet ngitung "4" sebelum ngunci
    -> cuma satu yg boleh masuk, total maksimal 5 (FOR UPDATE di baris link)."""
    with pg_app.app_context():
        user = register_user(f"pg.{uuid.uuid4().hex[:8]}@spindo.com", "PasswordKuat123", "PG", "ICT", "Staff")
        web_id = db.session.execute(db.select(Category.id).filter_by(name="Web", parent_id=None)).scalar_one()
        entry_dict = build_entry_dict(web_id)
        entry = create_access_entry(user, entry_dict, upload_file_list=[
            FileStorage(stream=io.BytesIO(PNG_BYTES), filename=f"lama{index}.png") for index in range(4)
        ])
        user_id, entry_id = user.id, entry.id

    original_prepare = attachment_service.prepare_upload_list

    def slow_prepare(*args, **kwargs):
        result = original_prepare(*args, **kwargs)
        time.sleep(0.5)  # biar dua request sama-sama udah ngitung sebelum ada yg ngunci
        return result

    monkeypatch.setattr("app.services.access_entry_service.prepare_upload_list", slow_prepare)

    def upload_one():
        from app.models import User

        user = db.session.get(User, user_id)
        entry = db.session.get(AccessEntry, entry_id)
        return update_access_entry(user, entry, entry_dict, upload_file_list=[
            FileStorage(stream=io.BytesIO(PNG_BYTES), filename="baru.png"),
        ])

    result_list = run_together(pg_app, [upload_one, upload_one])
    assert sorted(kind for kind, _ in result_list) == ["error", "ok"]
    assert isinstance(next(value for kind, value in result_list if kind == "error"), ValidationError)
    with pg_app.app_context():
        assert db.session.scalar(db.select(db.func.count(Attachment.id)).where(Attachment.access_entry_id == entry_id)) == 5


def test_concurrent_category_names_differing_case(pg_app, monkeypatch):
    """Negative: 2 admin barengan bikin "Server X" & "SERVER X", dua-duanya lolos cek nama -> index unik lower(name)
    nolak satu, & yg kalah dapet pesan validasi (bukan error 500)."""
    with pg_app.app_context():
        admin = register_user(f"pg.admin.{uuid.uuid4().hex[:8]}@spindo.com", "PasswordKuat123", "PG", "ICT", "Staff", role="admin")
        admin_id = admin.id
    name = f"Server {uuid.uuid4().hex[:6]}"

    def slow_find(*args, **kwargs):
        time.sleep(0.5)
        return None

    monkeypatch.setattr(category_service, "find_sibling_by_name", slow_find)

    def create(category_name):
        from app.models import User

        return lambda: category_service.create_category(db.session.get(User, admin_id), {"name": category_name, "description": ""}).id

    result_list = run_together(pg_app, [create(name), create(name.upper())])
    assert sorted(kind for kind, _ in result_list) == ["error", "ok"]
    assert isinstance(next(value for kind, value in result_list if kind == "error"), ValidationError)


def test_audit_log_cannot_be_changed(pg_app):
    """Negative (security): trigger dari migrasi nolak UPDATE/DELETE audit_logs, termasuk lewat SQL langsung."""
    from sqlalchemy.exc import DBAPIError

    with pg_app.app_context():
        # bikin akun = 1 baris audit log baru
        user = register_user(f"pg.audit.{uuid.uuid4().hex[:8]}@spindo.com", "PasswordKuat123", "PG", "ICT", "Staff")
        audit_id = db.session.scalar(db.select(AuditLog.id).where(AuditLog.user_id == user.id).limit(1))
        assert audit_id is not None
        with pytest.raises(DBAPIError):
            db.session.execute(db.text("UPDATE audit_logs SET actor_email = 'palsu' WHERE id = :id"), {"id": audit_id})
        db.session.rollback()
        with pytest.raises(DBAPIError):
            db.session.execute(db.text("DELETE FROM audit_logs WHERE id = :id"), {"id": audit_id})
        db.session.rollback()


def test_concurrent_admin_demotion_keeps_one_admin(pg_app, monkeypatch):
    """Negative (temuan audit): 2 perintah unset-admin barengan buat 2 admin terakhir yg beda -> satu ditolak,
    minimal tetep nyisa 1 admin aktif (baris admin dikunci sebelum dihitung)."""
    from app.models import User
    from app.services import user_service

    with pg_app.app_context():
        # admin lain yg udah ada di database test dijadiin non-admin dulu, biar tinggal 2 admin
        db.session.execute(db.update(User).where(User.role == "admin").values(role="user_entry"))
        db.session.commit()
        admin_id_list = [
            register_user(f"pg.last.{uuid.uuid4().hex[:8]}@spindo.com", "PasswordKuat123", "PG", "ICT", "Staff", role="admin").id
            for _ in range(2)
        ]
    original_audit_dict = user_service.build_user_admin_audit_dict

    def slow_audit_dict(user):
        time.sleep(0.5)  # nahan transaksi pertama di antara cek & simpan
        return original_audit_dict(user)

    monkeypatch.setattr(user_service, "build_user_admin_audit_dict", slow_audit_dict)

    def demote(user_id):
        return lambda: user_service.change_user_role(None, db.session.get(User, user_id), "user_entry").id

    result_list = run_together(pg_app, [demote(admin_id) for admin_id in admin_id_list])
    assert sorted(kind for kind, _ in result_list) == ["error", "ok"]
    with pg_app.app_context():
        assert db.session.scalar(db.select(db.func.count(User.id)).where(User.role == "admin", User.is_active.is_(True))) == 1


def make_admin_and_category(pg_app):
    with pg_app.app_context():
        admin = register_user(f"pg.cat.{uuid.uuid4().hex[:8]}@spindo.com", "PasswordKuat123", "PG", "ICT", "Staff", role="admin")
        category = category_service.create_category(admin, {"name": f"Hapus {uuid.uuid4().hex[:6]}", "description": ""})
        return admin.id, category.id


def slow_child_count(monkeypatch):
    original_count = category_service.count_child_category

    def slow_count(category_id):
        result = original_count(category_id)
        time.sleep(0.5)  # nahan transaksi hapus di antara cek & hapus
        return result

    monkeypatch.setattr(category_service, "count_child_category", slow_count)


def test_concurrent_delete_same_category(pg_app, monkeypatch):
    """Negative (temuan audit): 2 admin hapus kategori yg sama barengan -> satu berhasil, satu dapet pesan
    "already deleted" (bukan error), & audit hapusnya cuma 1."""
    from app.models import User

    admin_id, category_id = make_admin_and_category(pg_app)
    slow_child_count(monkeypatch)

    def delete():
        return category_service.delete_category(db.session.get(User, admin_id), db.session.get(Category, category_id))

    result_list = run_together(pg_app, [delete, delete])
    assert sorted(kind for kind, _ in result_list) == ["error", "ok"]
    assert isinstance(next(value for kind, value in result_list if kind == "error"), ValidationError)
    with pg_app.app_context():
        assert db.session.scalar(db.select(db.func.count(AuditLog.id)).where(
            AuditLog.entity_type == "categories", AuditLog.entity_id == str(category_id), AuditLog.action == "delete",
        )) == 1


def test_delete_category_while_sub_added_never_errors(pg_app, monkeypatch):
    """Negative (temuan audit): hapus kategori barengan orang nambah sub di dalemnya -> salah satu ditolak pake
    pesan validasi (bukan error 500), & ga ada sub-kategori yatim."""
    from app.models import User

    admin_id, category_id = make_admin_and_category(pg_app)
    slow_child_count(monkeypatch)

    def delete():
        return category_service.delete_category(db.session.get(User, admin_id), db.session.get(Category, category_id))

    def add_sub():
        time.sleep(0.2)  # masuk pas transaksi hapus udah ngitung sub (0) tapi belum ngehapus
        parent = db.session.get(Category, category_id)
        return category_service.create_sub_category(db.session.get(User, admin_id), parent, {"name": "Sub", "description": ""}).id

    result_list = run_together(pg_app, [delete, add_sub])
    assert all(kind == "ok" or isinstance(value, ValidationError) for kind, value in result_list), result_list
    with pg_app.app_context():
        parent = db.session.get(Category, category_id)
        sub_count = db.session.scalar(db.select(db.func.count(Category.id)).where(Category.parent_id == category_id))
        assert parent is not None or sub_count == 0
