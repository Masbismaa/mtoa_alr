"""Test cek file upload (ekstensi + magic bytes)."""
import pytest
import io
import zipfile

from app.security.file_validator import clean_display_filename, detect_content_type


def test_legacy_doc_signature_alone_is_not_accepted():
    with pytest.raises(ValueError, match="tidak diizinkan"):
        detect_content_type("fake.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1not-a-word-document")


def test_office_zip_requires_main_part_and_relationships():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/fake.xml", "<fake/>")
    with pytest.raises(ValueError):
        detect_content_type("fake.docx", buffer.getvalue())


def test_embedded_object_in_office_is_rejected(sample_file_dict):
    buffer = io.BytesIO(sample_file_dict["docx"])
    with zipfile.ZipFile(buffer, "a") as archive:
        archive.writestr("word/embeddings/oleObject1.bin", b"dummy")
    with pytest.raises(ValueError):
        detect_content_type("embedded.docx", buffer.getvalue())


def test_valid_png_jpg_pdf(sample_file_dict):
    """Positive: gambar & pdf asli lolos, content type sesuai."""
    assert detect_content_type("foto.png", sample_file_dict["png"]) == ("png", "image/png")
    assert detect_content_type("foto.JPG", sample_file_dict["jpg"]) == ("jpg", "image/jpeg")
    assert detect_content_type("manual.pdf", sample_file_dict["pdf"])[1] == "application/pdf"

def test_fake_pdf_rejected(sample_file_dict):
    """Negative (security): file exe yg namanya diganti .pdf ketahuan."""
    with pytest.raises(ValueError, match="tidak sesuai"):
        detect_content_type("tagihan.pdf", sample_file_dict["exe"])

def test_extension_not_allowed(sample_file_dict):
    """Negative (security): exe, html, svg, tanpa ekstensi ditolak."""
    for filename in ["setup.exe", "halaman.html", "logo.svg", "tanpa_ekstensi"]:
        with pytest.raises(ValueError, match="tidak diizinkan"):
            detect_content_type(filename, sample_file_dict["png"])

def test_valid_docx(sample_file_dict):
    """Positive: docx dgn struktur zip yg bener lolos."""
    extension, _ = detect_content_type("laporan.docx", sample_file_dict["docx"])
    assert extension == "docx"

def test_docx_with_macro_rejected(sample_file_dict):
    """Negative (security): docx bermakro ditolak."""
    with pytest.raises(ValueError):
        detect_content_type("laporan.docx", sample_file_dict["docx_macro"])

def test_docx_content_renamed_to_xlsx_rejected(sample_file_dict):
    """Negative: isi docx tapi namanya .xlsx ditolak (folder xl/ ga ada)."""
    with pytest.raises(ValueError):
        detect_content_type("data.xlsx", sample_file_dict["docx"])

def test_txt_rules(sample_file_dict):
    """Positive & negative: teks biasa lolos, file biner ber-ekstensi .txt ditolak."""
    assert detect_content_type("catatan.txt", sample_file_dict["txt"])[0] == "txt"
    with pytest.raises(ValueError):
        detect_content_type("catatan.txt", sample_file_dict["exe"])

def test_empty_file_rejected():
    """Negative: file kosong ditolak."""
    with pytest.raises(ValueError, match="kosong"):
        detect_content_type("kosong.pdf", b"")

def test_clean_display_filename_strips_path():
    """Negative (security): path traversal & tag HTML dibuang dari nama file."""
    assert clean_display_filename("..\\..\\windows\\evil.pdf") == "evil.pdf"
    assert clean_display_filename("../../etc/passwd.txt") == "passwd.txt"
    assert clean_display_filename("<b>laporan</b>.pdf") == "laporan.pdf"
