"""Unit test untuk route health check dan validasi konfigurasi aplikasi."""

import pytest

from app import create_app
from app.config import TestingConfig


def test_health_check_returns_ok(client):
    """Positive: /health harus mengembalikan HTTP 200 dan status 'ok'."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_unknown_route_returns_404(client):
    """Negative: URL yang tidak terdaftar harus mengembalikan HTTP 404."""
    response = client.get("/halaman-tidak-ada")
    assert response.status_code == 404


def test_create_app_without_secret_key_raises_error(monkeypatch):
    """Negative (security): aplikasi wajib menolak jalan jika SECRET_KEY kosong."""
    # Kosongkan SECRET_KEY sementara (otomatis dikembalikan setelah test selesai)
    monkeypatch.setattr(TestingConfig, "SECRET_KEY", None)
    with pytest.raises(RuntimeError):
        create_app("testing")