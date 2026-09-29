"""Cek file upload: ekstensi + isi file beneran (magic bytes), bukan cuma percaya nama file."""
import io
import re
import zipfile

from app.utils.constants import ATTACHMENT_CONTENT_TYPE_BY_EXTENSION_DICT, ATTACHMENT_EXTENSION_LIST, MAX_FILENAME_LENGTH
from app.utils.sanitizer import sanitize_text

# byte awal khas tiap format
SIGNATURE_BY_EXTENSION_DICT = {
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "pdf": [b"%PDF-"],
    "doc": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
}

# xlsx & docx itu sebenernya file zip, dicek isinya
OFFICE_FOLDER_BY_EXTENSION_DICT = {"xlsx": "xl/", "docx": "word/"}
ZIP_SIGNATURE = b"PK\x03\x04"
OFFICE_CONTENT_TYPE_FILE = "[Content_Types].xml"
MACRO_FILE_NAME = "vbaProject.bin"

UTF16_BOM_LIST = [b"\xff\xfe", b"\xfe\xff"]

def clean_display_filename(filename):
    """Nama file buat ditampilin: buang tag HTML dulu, baru buang path (..\\..\\)."""
    # tag HTML dibuang duluan, soalnya </b> juga ada garis miringnya
    clean_text = sanitize_text(filename or "", max_length=4096) or ""
    base_name = re.split(r"[\\/]", clean_text)[-1]
    return base_name.strip(". ")[:MAX_FILENAME_LENGTH] or "file"

def get_file_extension(filename):
    """Ambil ekstensi huruf kecil, misal 'Laporan.PDF' -> 'pdf'."""
    _, dot, extension = (filename or "").rpartition(".")
    return extension.lower() if dot else ""

def is_valid_office_zip(content_bytes, extension):
    """xlsx/docx asli: zip yg punya [Content_Types].xml + folder xl/ atau word/, tanpa makro."""
    try:
        with zipfile.ZipFile(io.BytesIO(content_bytes)) as zip_file:
            name_list = zip_file.namelist()
    except zipfile.BadZipFile:
        return False

    if OFFICE_CONTENT_TYPE_FILE not in name_list:
        return False
    # file bermakro ditolak
    if any(name.endswith(MACRO_FILE_NAME) for name in name_list):
        return False
    return any(name.startswith(OFFICE_FOLDER_BY_EXTENSION_DICT[extension]) for name in name_list)

def is_valid_text(content_bytes):
    """txt: teks biasa (UTF-8 / ANSI Windows / UTF-16 dari Notepad), bukan file biner."""
    if any(content_bytes.startswith(bom) for bom in UTF16_BOM_LIST):
        try:
            content_bytes.decode("utf-16")
            return True
        except UnicodeDecodeError:
            return False

    # ada byte nol = hampir pasti file biner
    if b"\x00" in content_bytes:
        return False
    for encoding in ("utf-8", "cp1252"):
        try:
            content_bytes.decode(encoding)
            return True
        except UnicodeDecodeError:
            continue
    return False

def detect_content_type(filename, content_bytes):
    """Cek file boleh diupload atau nggak. Return (ekstensi, content_type), lempar ValueError kalau ditolak."""
    extension = get_file_extension(filename)
    if extension not in ATTACHMENT_CONTENT_TYPE_BY_EXTENSION_DICT:
        raise ValueError(f"tipe file tidak diizinkan (yang boleh: {', '.join(ATTACHMENT_EXTENSION_LIST)})")
    if not content_bytes:
        raise ValueError("file kosong")

    if extension in SIGNATURE_BY_EXTENSION_DICT:
        is_valid = any(content_bytes.startswith(signature) for signature in SIGNATURE_BY_EXTENSION_DICT[extension])
    elif extension in OFFICE_FOLDER_BY_EXTENSION_DICT:
        is_valid = content_bytes.startswith(ZIP_SIGNATURE) and is_valid_office_zip(content_bytes, extension)
    else:
        is_valid = is_valid_text(content_bytes)

    if not is_valid:
        raise ValueError(f"isi file tidak sesuai dengan ekstensi .{extension} (atau berisi makro)")
    return extension, ATTACHMENT_CONTENT_TYPE_BY_EXTENSION_DICT[extension]