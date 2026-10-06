"""Route health check untuk memastikan aplikasi berjalan (dipakai monitoring/CI)."""

from flask import Blueprint, jsonify

# Blueprint = kumpulan route yang didaftarkan ke aplikasi di app/__init__.py
health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health_check():
    """Cek aplikasi hidup, balikin {"status": "ok"}. Sengaja ga nyebut nama/versi app."""
    return jsonify({"status": "ok"})