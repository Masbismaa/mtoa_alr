"""Test fail-fast config di create_app."""

import pytest

from app import create_app
from app.config import TestingConfig

def test_create_app_without_encryption_key_raises_error(monkeypatch):
    """Negative: app wajib nolak jalan kalau ENCRYPTION_KEY kosong."""
    monkeypatch.setattr(TestingConfig, "ENCRYPTION_KEY", None)
    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
        create_app("testing")

def test_create_app_with_invalid_encryption_key_raises_error(monkeypatch):
    """Negative: key yg formatnya salah juga harus ketahuan pas start."""
    monkeypatch.setattr(TestingConfig, "ENCRYPTION_KEY", "key-asal-asalan")
    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
        create_app("testing")