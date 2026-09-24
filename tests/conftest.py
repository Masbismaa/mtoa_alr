"""Fixture Pytest yang dipakai bersama oleh semua file test (DRY)."""

import pytest

from app import create_app
from app.extensions import db


@pytest.fixture()
def app():
    """Membuat aplikasi testing + tabel di SQLite memori; dibersihkan setelah tiap test."""
    app = create_app("testing")
    with app.app_context():
        # --- Setup: buat semua tabel kosong ---
        db.create_all()
        yield app
        # --- Teardown: tutup session & hapus semua tabel ---
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    """Membuat test client untuk mensimulasikan request HTTP ke aplikasi."""
    return app.test_client()