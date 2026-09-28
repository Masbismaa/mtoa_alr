"""Test validasi URL, address, dan port (SR-06)."""

import pytest

from app.utils.url_helper import normalize_address, normalize_url, parse_port


def test_normalize_url_lowercases_host_and_strips_slash():
    """Positive: skema & host jadi huruf kecil, garis miring akhir dibuang, path tetep."""
    assert normalize_url("  HTTPS://Intra.Spindo.COM/App/  ") == "https://intra.spindo.com/App"
    assert normalize_url("http://10.0.0.5:8080/") == "http://10.0.0.5:8080"


def test_normalize_url_rejects_non_http_scheme():
    """Negative (security): javascript: & ftp: ditolak."""
    for bad_url in ["javascript:alert(1)", "ftp://files.spindo.com", "intra.spindo.com"]:
        with pytest.raises(ValueError):
            normalize_url(bad_url)


def test_normalize_url_rejects_empty_and_spaces():
    """Negative: kosong / ada spasi ditolak."""
    with pytest.raises(ValueError, match="wajib"):
        normalize_url("")
    with pytest.raises(ValueError, match="spasi"):
        normalize_url("https://intra spindo.com")


def test_normalize_url_rejects_credentials_in_url():
    """Negative (security): username/password di dalem URL ditolak."""
    with pytest.raises(ValueError, match="Username"):
        normalize_url("https://admin:rahasia@intra.spindo.com")


def test_normalize_url_rejects_invalid_port():
    """Negative: port di URL yg ngaco ditolak."""
    with pytest.raises(ValueError):
        normalize_url("https://intra.spindo.com:99999")


def test_normalize_address_rules():
    """Positive & negative: address dirapihin, karakter aneh ditolak."""
    assert normalize_address(" Router-LT2.Local ") == "router-lt2.local"
    with pytest.raises(ValueError):
        normalize_address("10.0.0.1; rm -rf /")


def test_parse_port_rules():
    """Positive & negative: port 1-65535, kosong jadi None."""
    assert parse_port("22") == 22
    assert parse_port("") is None
    for bad_port in ["0", "70000", "abc"]:
        with pytest.raises(ValueError):
            parse_port(bad_port)