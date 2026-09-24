"""Fixture Pytest yang dipakai bersama oleh semua file test (DRY)."""

import pytest

from app import create_app


@pytest.fixture()
def app():
    """Membuat aplikasi dengan konfigurasi testing (tanpa PostgreSQL)."""
    return create_app("testing")


@pytest.fixture()
def client(app):
    """Membuat test client untuk mensimulasikan request HTTP ke aplikasi."""
    return app.test_client()