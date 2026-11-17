"""Route health check: /health (proses web hidup) & /health/ready (siap nerima user: DB, Redis, dll nyambung)."""
import os
import time

from flask import Blueprint, current_app, jsonify

from app.extensions import db

# Blueprint = kumpulan route yang didaftarkan ke aplikasi di app/__init__.py
health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health_check():
    """Liveness: cuma {"status": "ok"}, ga nyentuh DB."""
    # sengaja ga cek DB: DB gangguan sebentar jangan sampe bikin service manager restart aplikasi
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


READINESS_CHECK_DICT = {
    "database": check_database,
    "limit_storage": check_limit_storage,
    "upload_folder": check_upload_folder,
}


# hasil cek di-cache sebentar per proses; bukan rate limiter karena Redis-nya ikut dicek
READINESS_CACHE_SECONDS = 5
readiness_cache = {"expires_at": 0.0, "response": None}


@health_bp.get("/health/ready")
def readiness_check():
    """Readiness: 200 kalau layanan pendukung nyambung, 503 + nama yg gagal kalau putus."""
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
        result_dict[name] = "ok" if is_ok else "failed"
    is_ready = "failed" not in result_dict.values()
    response = ({"status": "ready" if is_ready else "not_ready", "checks": result_dict}, 200 if is_ready else 503)
    readiness_cache.update(expires_at=time.monotonic() + READINESS_CACHE_SECONDS, response=response)
    return jsonify(response[0]), response[1]
