"""Penanganan pesan validasi formulir yang digunakan oleh beberapa route."""
from flask import flash


def flash_error_list(error_list):
    """Tampilkan setiap pesan validasi sebagai notifikasi kesalahan."""
    for error_dict in error_list:
        flash(error_dict["message"], "danger")
