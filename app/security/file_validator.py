"""Cek file upload: ekstensi + isi file beneran (magic bytes), bukan cuma percaya nama file."""
import io
import re
import zipfile
from pathlib import PurePosixPath
from xml.etree import ElementTree

from app.utils.constants import ATTACHMENT_CONTENT_TYPE_BY_EXTENSION_DICT, ATTACHMENT_EXTENSION_LIST, MAX_FILENAME_LENGTH
from app.utils.sanitizer import sanitize_text

# byte awal khas tiap format
SIGNATURE_BY_EXTENSION_DICT = {
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "pdf": [b"%PDF-"],
}

# xlsx & docx itu sebenernya file zip, dicek isinya
OFFICE_FOLDER_BY_EXTENSION_DICT = {"xlsx": "xl/", "docx": "word/"}
ZIP_SIGNATURE = b"PK\x03\x04"
OFFICE_CONTENT_TYPE_FILE = "[Content_Types].xml"

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
    """Periksa paket OOXML, batasi hasil dekompresi, tolak bagian aktif/tertanam."""
    main_part = "xl/workbook.xml" if extension == "xlsx" else "word/document.xml"
    main_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml" if extension == "xlsx"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
    )
    try:
        with zipfile.ZipFile(io.BytesIO(content_bytes)) as zip_file:
            info_list = zip_file.infolist()
            names = [info.filename for info in info_list]
            if len(names) > 2000 or len(names) != len(set(names)):
                return False
            if sum(info.file_size for info in info_list) > 50 * 1024 * 1024:
                return False
            if not {OFFICE_CONTENT_TYPE_FILE, "_rels/.rels", main_part}.issubset(names):
                return False
            for info in info_list:
                name = info.filename.lower()
                if (PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts or "\\" in name
                        or info.flag_bits & 1 or info.file_size > 10 * 1024 * 1024
                        or info.file_size > max(info.compress_size, 1) * 200
                        or any(part in name for part in ("vbaproject", "/embeddings/", "/activex/"))):
                    return False
            types_xml = zip_file.read(OFFICE_CONTENT_TYPE_FILE)
            relations_xml = zip_file.read("_rels/.rels")
            main_xml = zip_file.read(main_part)
            for xml in (types_xml, relations_xml, main_xml):
                if b"\0" in xml or b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
                    return False
            types = ElementTree.fromstring(types_xml)
            relationships = ElementTree.fromstring(relations_xml)
            main = ElementTree.fromstring(main_xml)
            expected_main = ("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}workbook"
                             if extension == "xlsx" else "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document")
            if (types.tag != "{http://schemas.openxmlformats.org/package/2006/content-types}Types"
                    or relationships.tag != "{http://schemas.openxmlformats.org/package/2006/relationships}Relationships"
                    or main.tag != expected_main):
                return False
            has_type = any(node.get("PartName") == "/" + main_part and node.get("ContentType") == main_type
                           for node in types)
            has_main = any(node.get("Target", "").lstrip("/") == main_part
                           and node.get("Type", "").endswith("/officeDocument")
                           and node.get("TargetMode") != "External" for node in relationships)
            if any("macroenabled" in node.get("ContentType", "").lower() for node in types):
                return False
            return has_type and has_main
    except (zipfile.BadZipFile, ElementTree.ParseError, KeyError, RuntimeError, OSError, ValueError):
        return False

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
