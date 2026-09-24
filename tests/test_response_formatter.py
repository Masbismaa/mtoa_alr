"""Test pembersihan input (anti XSS)."""

from app.utils.sanitizer import sanitize_text

def test_sanitize_removes_script_tag():
    """tag script beserta isinya dibuang."""
    assert sanitize_text("<script>alert(1)</script>Halo") == "Halo"

def test_sanitize_strips_html_tags_keeps_text():
    """tag HTML biasa dibuang, teksnya tetep ada."""
    assert sanitize_text("<b>tebal</b> teks") == "tebal teks"

def test_sanitize_keeps_normal_special_characters():
    """simbol biasa kayak & dan < ga boleh rusak."""
    assert sanitize_text("R&D lantai 2 < 5 orang") == "R&D lantai 2 < 5 orang"

def test_sanitize_removes_control_chars_and_trims():
    """null byte dibuang, spasi di ujung dirapihin."""
    assert sanitize_text("  halo\x00dunia  ") == "halodunia"

def test_sanitize_cuts_to_max_length():
    """teks kepanjangan dipotong."""
    assert sanitize_text("a" * 50, max_length=10) == "a" * 10

def test_sanitize_none_returns_none():
    """None tetep None."""
    assert sanitize_text(None) is None