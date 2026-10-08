"""Nulis tag <script>/<link> buat komponen React hasil build Vite (folder frontend/).

Vite ngasih nama file ber-hash (misal entry_table-3f9a1c.js) biar cache browser ga nyangkut pas ada versi baru.
Nama aslinya dicatat di app/static/dist/.vite/manifest.json, file itu yg dibaca di sini.
Cara pake di template: {{ vite_tags("entry_table") }}  (nama entry = kunci di rollupOptions.input vite.config.js)
"""
import json
from pathlib import Path

from flask import current_app, url_for
from markupsafe import Markup, escape

MANIFEST_RELATIVE_PATH = Path("dist") / ".vite" / "manifest.json"
DIST_FOLDER = "dist"

# isi manifest disimpen sekali per proses; kalau file-nya berubah (build ulang pas development) dibaca lagi
_manifest_cache = {"mtime": None, "data": None}

def read_manifest():
    """Isi manifest.json. Belum di-build -> error yg jelas cara benerinnya."""
    manifest_path = Path(current_app.static_folder) / MANIFEST_RELATIVE_PATH
    try:
        mtime = manifest_path.stat().st_mtime
    except FileNotFoundError:
        raise RuntimeError(
            f"{manifest_path} belum ada. Build komponen React dulu: cd frontend && npm ci && npm run build"
        ) from None
    if _manifest_cache["mtime"] != mtime:
        _manifest_cache["data"] = json.loads(manifest_path.read_text(encoding="utf-8"))
        _manifest_cache["mtime"] = mtime
    return _manifest_cache["data"]

def find_manifest_item(manifest, entry_name):
    """Cari data entry di manifest. Kuncinya path sumber (src/entry_table/main.jsx), yg dicocokin field name-nya."""
    for item in manifest.values():
        if item.get("isEntry") and item.get("name") == entry_name:
            return item
    raise RuntimeError(f'Entry Vite "{entry_name}" ga ada di manifest. Cek rollupOptions.input di frontend/vite.config.js')

def build_static_url(file_name):
    """URL file di folder static/dist."""
    return url_for("static", filename=f"{DIST_FOLDER}/{file_name}")

def vite_tags(entry_name):
    """Tag CSS + script module buat satu entry. Script module otomatis defer, jadi aman ditaruh di mana aja."""
    item = find_manifest_item(read_manifest(), entry_name)
    tag_list = [
        f'<link rel="stylesheet" href="{escape(build_static_url(css_file))}">' for css_file in item.get("css", [])
    ]
    tag_list.append(f'<script type="module" src="{escape(build_static_url(item["file"]))}"></script>')
    return Markup("\n".join(tag_list))
