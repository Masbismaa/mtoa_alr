"""Route health check: /health (proses web hidup) & /health/ready (siap nerima user: DB, Redis, dll nyambung)."""
import os
import time

from flask import Blueprint, current_app, jsonify

from app.extensions import db

# Blueprint = kumpulan route yang didaftarkan ke aplikasi di app/__init__.py
health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health_check():
    """Liveness: proses web hidup, balikin {"status": "ok"}. Sengaja ga nyebut nama/versi app & ga nyentuh DB,
    biar service manager ga restart aplikasi cuma gara-gara DB lagi gangguan sebentar."""
    return jsonify({"status": "ok"})


def check_database():
    db.session.execute(db.text("SELECT 1"))
    db.session.rollback()
    return True


def check_limit_storage():
    """Penyimpanan rate limit & blokir login (memory di laptop, Redis di production)."""
    return current_app.extensions["auth_throttle"].storage.check()


def check_upload_folder():
    """Folder lampiran ada (dibikin kalau belum, sama kayak pas upload) & bisa ditulis."""
    from app.services.attachment_service import get_upload_folder

    return os.access(get_upload_folder(), os.W_OK)


def check_scanner():
    from app.security.upload_scanner import ping_scanner

    return ping_scanner()


READINESS_CHECK_DICT = {
    "database": check_database,
    "limit_storage": check_limit_storage,
    "upload_folder": check_upload_folder,
    "upload_scanner": check_scanner,
}


# hasil cek disimpen sebentar per proses: dipanggil beruntun ga bikin DB/Redis/ClamAV kebanjiran. Sengaja bukan
# rate limiter (Flask-Limiter nyimpen hitungan di Redis, yg justru lagi dicek: Redis mati = 500, bukan laporan 503)
READINESS_CACHE_SECONDS = 5
readiness_cache = {"expires_at": 0.0, "response": None}


@health_bp.get("/health/ready")
def readiness_check():
    """Readiness: dipake load balancer / monitoring sebelum ngarahin user ke server ini.
    200 kalau semua layanan pendukung nyambung, 503 + nama yg gagal kalau ada yg putus.
    Detail error sengaja ga ditampilin (bisa bocorin alamat/kredensial), cukup dicatat di log server."""
    if time.monotonic() < readiness_cache["expires_at"]:
        result_dict, status_code = readiness_cache["response"]
        return jsonify(result_dict), status_code
    result_dict = {}
    for name, check in READINESS_CHECK_DICT.items():
        try:
            is_ok = check()
        except Exception:  # noqa: BLE001 - layanan putus apa pun bentuk error-nya = belum siap
            current_app.logger.exception("Readiness check %s gagal", name)
            is_ok = False
        # None = belum diatur di environment ini (misal scanner di laptop), ga dianggap gagal
        result_dict[name] = "skipped" if is_ok is None else ("ok" if is_ok else "failed")
    is_ready = "failed" not in result_dict.values()
    response = ({"status": "ready" if is_ready else "not_ready", "checks": result_dict}, 200 if is_ready else 503)
    readiness_cache.update(expires_at=time.monotonic() + READINESS_CACHE_SECONDS, response=response)
    return jsonify(response[0]), response[1]
