"""Test helper baca parameter URL."""
from datetime import date
from werkzeug.datastructures import MultiDict
from app.utils.query_helper import clean_keyword_arg, parse_date_arg
from app.utils.selection import build_selection_query_dict, text_field

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

def test_build_selection_query_dict():
    """Positive: cuma kriteria yg dikenal & ga kosong yg dibawa ke link halaman berikutnya."""
    args = MultiDict([("q", "vpn"), ("title", "portal*"), ("title__not", ""), ("hack", "x")])
    assert build_selection_query_dict(args, [text_field("title", "Judul")]) == {"q": ["vpn"], "title": ["portal*"]}