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

def build_docx_with_lying_header(real_size, fake_size=1000):
    """docx yg document.xml-nya isinya real_size byte nol, tapi header zip ngaku cuma fake_size byte."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("_rels/.rels", "<Relationships/>")
        archive.writestr("word/document.xml", b"\0" * real_size)
    data = bytearray(buffer.getvalue())
    name = b"word/document.xml"
    # file_size di local header (offset 22) & central directory (offset 24) dipalsuin
    for signature, size_offset, name_offset, length_offset in ((b"PK\x03\x04", 22, 30, 26), (b"PK\x01\x02", 24, 46, 28)):
        position = data.find(signature)
        while position != -1:
            name_length = int.from_bytes(data[position + length_offset: position + length_offset + 2], "little")
            if data[position + name_offset: position + name_offset + name_length] == name:
                data[position + size_offset: position + size_offset + 4] = fake_size.to_bytes(4, "little")
            position = data.find(signature, position + 4)
    return bytes(data)

def test_zip_with_lying_size_rejected_without_using_much_memory():
    """Negative (security/zip bomb): header zip ngaku kecil padahal isinya 30 MB -> ditolak tanpa ngebuka semuanya ke RAM."""
    import tracemalloc

    bomb = build_docx_with_lying_header(30 * 1024 * 1024)
    tracemalloc.start()
    try:
        with pytest.raises(ValueError):
            detect_content_type("bom.docx", bomb)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 5 * 1024 * 1024

def test_docx_compressed_with_deflate_still_valid(sample_file_dict):
    """Positive: docx yg dikompres deflate (kayak file Word asli) tetep lolos."""
    source = zipfile.ZipFile(io.BytesIO(sample_file_dict["docx"]))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for info in source.infolist():
            archive.writestr(info.filename, source.read(info.filename))
    assert detect_content_type("laporan.docx", buffer.getvalue())[0] == "docx"

def test_docx_with_unusual_compression_rejected(sample_file_dict):
    """Negative (security): metode kompresi selain stored/deflate (misal bzip2) ditolak, Office ga pernah makai."""
    source = zipfile.ZipFile(io.BytesIO(sample_file_dict["docx"]))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_BZIP2) as archive:
        for info in source.infolist():
            archive.writestr(info.filename, source.read(info.filename))
    with pytest.raises(ValueError):
        detect_content_type("laporan.docx", buffer.getvalue())
