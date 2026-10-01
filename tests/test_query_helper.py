"""Test helper baca parameter URL."""
from datetime import date
from app.utils.query_helper import clean_keyword_arg, drop_empty_value, parse_date_arg

def test_parse_date_arg_valid():
    """Positive: format YYYY-MM-DD kebaca jadi date."""
    assert parse_date_arg("2026-09-29") == date(2026, 9, 29)

def test_parse_date_arg_invalid_returns_none():
    """Negative: tanggal ngaco / kosong -> None, ga bikin error."""
    assert parse_date_arg("kemarin") is None
    assert parse_date_arg("2026-13-40") is None
    assert parse_date_arg("") is None
    assert parse_date_arg(None) is None

def test_clean_keyword_arg_trims_and_limits():
    """Positive: spasi di ujung dibuang, kepanjangan dipotong 100 huruf."""
    assert clean_keyword_arg("  vpn  ") == "vpn"
    assert len(clean_keyword_arg("a" * 500)) == 100
    assert clean_keyword_arg(None) == ""

def test_drop_empty_value():
    """Positive: item kosong dibuang, sisanya tetep."""
    raw_dict = {"q": "vpn", "action": "", "date_from": None, "category_id": 3}
    assert drop_empty_value(raw_dict) == {"q": "vpn", "category_id": 3}