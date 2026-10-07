"""Fixture Pytest yang dipakai bareng semua file test."""
import io
import zipfile

import pytest
from werkzeug.datastructures import FileStorage

from app import create_app
from app.extensions import db
from app.services import auth_service

# data login yg dipake bareng
USER_PASSWORD = "PasswordKuat123"
FIXED_OTP_CODE = "123456"

@pytest.fixture()
def app(tmp_path):
    """App testing + tabel di SQLite memori + folder upload sementara."""
    app = create_app("testing")
    # lampiran test ditaruh di folder sementara, abis test otomatis dihapus pytest
    app.config["UPLOAD_FOLDER"] = str(tmp_path / "uploads")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture()
def client(app):
    """Test client buat nyimulasiin request."""
    return app.test_client()

@pytest.fixture()
def user_password():
    """Password contoh yg valid."""
    return USER_PASSWORD

@pytest.fixture()
def registered_user(app):
    """User yg udah terdaftar."""
    return auth_service.register_user(
        email="user.login@spindo.com",
        password=USER_PASSWORD,
        full_name="User Login",
        department="ICT",
        job_title="Staff",
    )

@pytest.fixture()
def fixed_otp_code(monkeypatch):
    """OTP selalu 123456 biar gampang dites."""
    monkeypatch.setattr(auth_service, "generate_otp_code", lambda: FIXED_OTP_CODE)
    return FIXED_OTP_CODE

def login_client(client, email, otp_code):
    """Helper: login 2 langkah (password + OTP)."""
    client.post("/auth/login", data={"email": email, "password": USER_PASSWORD})
    client.post("/auth/otp", data={"otp_code": otp_code})
    return client

@pytest.fixture()
def logged_in_client(client, registered_user, fixed_otp_code):
    """Client yg udah login sebagai registered_user."""
    return login_client(client, registered_user.email, fixed_otp_code)

@pytest.fixture()
def category_dict(app):
    """Kategori default udah di-seed: dict nama -> Category."""
    from app.models import Category
    from app.services.seed_service import seed_default_categories

    seed_default_categories()
    category_list = db.session.execute(db.select(Category)).scalars().all()
    return {category.name: category for category in category_list}

@pytest.fixture()
def other_user(app):
    """User kedua (buat ngetes data orang lain)."""
    return auth_service.register_user(
        email="user.lain@spindo.com",
        password=USER_PASSWORD,
        full_name="User Lain",
        department="Finance",
        job_title="Staff",
    )

@pytest.fixture()
def admin_user(app):
    """User ber-role admin."""
    from app.utils.constants import ROLE_ADMIN

    return auth_service.register_user(
        email="admin.fixture@spindo.com",
        password=USER_PASSWORD,
        full_name="Admin Fixture",
        department="ICT",
        job_title="Manager",
        role=ROLE_ADMIN,
    )

def build_office_zip_bytes(folder_name, has_macro=False):
    """Bikin file xlsx/docx palsu tapi strukturnya bener (zip)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        main_part = "xl/workbook.xml" if folder_name == "xl/" else "word/document.xml"
        main_type = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
                     if folder_name == "xl/" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml")
        zip_file.writestr("[Content_Types].xml", f'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/{main_part}" ContentType="{main_type}"/></Types>')
        zip_file.writestr("_rels/.rels", f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="{main_part}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"/></Relationships>')
        root_xml = ('<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets/></workbook>'
                    if folder_name == "xl/" else '<document xmlns="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><body/></document>')
        zip_file.writestr(main_part, root_xml)
        if has_macro:
            zip_file.writestr(f"{folder_name}vbaProject.bin", "makro")
    return buffer.getvalue()

@pytest.fixture()
def sample_file_dict():
    """Contoh isi file per format (cukup byte awalnya yg bener)."""
    return {
        "png": b"\x89PNG\r\n\x1a\n" + b"\x00" * 20,
        "jpg": b"\xff\xd8\xff\xe0" + b"\x00" * 20,
        "pdf": b"%PDF-1.4\n%contoh\n",
        "txt": "Halo dunia, ini catatan.".encode("utf-8"),
        "docx": build_office_zip_bytes("word/"),
        "docx_macro": build_office_zip_bytes("word/", has_macro=True),
        "exe": b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 20,
    }

@pytest.fixture()
def make_file_storage():
    """Pabrik FileStorage (objek file upload ala Flask) buat test service."""

    def build_file_storage(content_bytes, filename):
        return FileStorage(stream=io.BytesIO(content_bytes), filename=filename)

    return build_file_storage

@pytest.fixture()
def admin_client(client, admin_user, fixed_otp_code):
    """Client yg udah login sebagai admin_user."""
    return login_client(client, admin_user.email, fixed_otp_code)
