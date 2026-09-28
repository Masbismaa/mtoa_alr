"""Route health check untuk memastikan aplikasi berjalan (dipakai monitoring/CI)."""

from flask import Blueprint, jsonify

# Blueprint = kumpulan route yang didaftarkan ke aplikasi di app/__init__.py
health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health_check():
    """Mengembalikan status aplikasi dalam format JSON.

    Returns:
        JSON {"status": "ok", "app": "MTOA ALR"} dengan HTTP 200.
    """
    return jsonify({"status": "ok", "app": "MTOA ALR"})