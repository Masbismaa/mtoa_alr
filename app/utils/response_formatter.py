"""Format balasan JSON yg seragam buat semua endpoint API."""

from flask import jsonify, request

def wants_json_response():
    """True kalau yg minta itu script (fetch) yg nunggu JSON: body-nya JSON, atau header Accept lebih milih JSON
    daripada HTML. Navigasi browser biasa (Accept: text/html,...) tetep dapet halaman error HTML.
    Dipake handler error (CSRF, 403, 404, 429, 500, ...) biar script ga dapet HTML & nampilin "Respon server tidak valid"."""
    if request.is_json:
        return True
    accept = request.accept_mimetypes
    return accept["application/json"] > accept["text/html"]

def success_response(data=None, message="Success", status_code=200):
    """Balasan kalau request sukses."""
    return jsonify({
        "is_success": True,
        "message": message,
        "data": data,
        "error_list": [],
    }), status_code

def error_response(message="Something went wrong", status_code=400, error_list=None):
    """Balasan kalau request gagal. error_list isinya detail per field (kalau ada)."""
    return jsonify({
        "is_success": False,
        "message": message,
        "data": None,
        "error_list": error_list or [],
    }), status_code