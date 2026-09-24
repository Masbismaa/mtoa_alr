"""Format balasan JSON yg seragam buat semua endpoint API."""

from flask import jsonify

def success_response(data=None, message="Berhasil", status_code=200):
    """Balasan kalau request sukses."""
    return jsonify({
        "is_success": True,
        "message": message,
        "data": data,
        "error_list": [],
    }), status_code

def error_response(message="Terjadi kesalahan", status_code=400, error_list=None):
    """Balasan kalau request gagal. error_list isinya detail per field (kalau ada)."""
    return jsonify({
        "is_success": False,
        "message": message,
        "data": None,
        "error_list": error_list or [],
    }), status_code