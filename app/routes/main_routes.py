"""Halaman utama setelah login."""
from flask import Blueprint, render_template
from flask_login import login_required

main_bp = Blueprint("main", __name__)

@main_bp.get("/")
@login_required
def home():
    """Beranda sementara buat mastiin login berhasil."""
    return render_template("pages/home.html")