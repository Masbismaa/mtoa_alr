"""Test fail-fast config di create_app."""

import pytest

from app import create_app
from app.config import TestingConfig

def test_create_app_without_secret_key_raises_error(monkeypatch):
    """Negative: app wajib nolak jalan kalau SECRET_KEY kosong."""
    monkeypatch.setattr(TestingConfig, "SECRET_KEY", None)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app("testing")
