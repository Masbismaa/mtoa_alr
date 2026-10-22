"""Test pembersihan input (anti XSS)."""
from app.utils.sanitizer import get_plain_text, sanitize_rich_text, sanitize_text

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

def test_sanitize_rich_text_keeps_format_and_drops_script():
    """Negative (security): tag format tetep, script beserta isinya dibuang."""
    cleaned_html = sanitize_rich_text("<b>tebal</b><ul><li>satu</li></ul><script>alert(1)</script>")
    assert "<b>tebal</b>" in cleaned_html
    assert "<li>satu</li>" in cleaned_html
    assert "script" not in cleaned_html

def test_sanitize_rich_text_drops_event_attribute():
    """Negative (security): atribut onclick/style dibuang."""
    cleaned_html = sanitize_rich_text('<p onclick="hack()" style="color:red">hai</p>')
    assert cleaned_html == "<p>hai</p>"

def test_sanitize_rich_text_keeps_word_like_format():
    """Positive: heading, quote, garis, coret, rata tengah, font/ukuran/warna dari toolbar tetep ada."""
    raw_html = ('<h1>Judul</h1><blockquote>kutipan</blockquote><hr><strike>coret</strike>'
                '<p style="text-align: center;">tengah</p><p align="right">kanan</p>'
                '<font face="Times New Roman" size="5" color="#d63939">merah</font>')
    cleaned_html = sanitize_rich_text(raw_html)
    for part in ["<h1>Judul</h1>", "<blockquote>kutipan</blockquote>", "<hr>", "<strike>coret</strike>",
                 '<p style="text-align:center">tengah</p>', '<p align="right">kanan</p>',
                 '<font face="Times New Roman" size="5" color="#d63939">merah</font>']:
        assert part in cleaned_html

def test_sanitize_rich_text_drops_value_outside_toolbar():
    """Negative (security): font/warna/ukuran di luar pilihan toolbar & CSS selain rata/indent dibuang."""
    cleaned_html = sanitize_rich_text('<font face="Comic Sans" size="9" color="red">x</font>'
                                      '<p style="background:url(javascript:alert(1));text-align:left">y</p>')
    assert cleaned_html == '<font>x</font><p style="text-align:left">y</p>'

def test_sanitize_rich_text_link_rules():
    """Negative (security): link javascript: dibuang, link https tetep + dikasih rel aman."""
    bad_html = sanitize_rich_text('<a href="javascript:alert(1)">klik</a>')
    good_html = sanitize_rich_text('<a href="https://intra.spindo.com">intra</a>')
    assert "javascript" not in bad_html
    assert "klik" in bad_html
    assert 'href="https://intra.spindo.com"' in good_html
    assert 'rel="noopener noreferrer"' in good_html

def test_get_plain_text_of_empty_editor():
    """Positive: editor yg isinya cuma tag kosong dianggap kosong."""
    assert get_plain_text("<ul><li></li></ul><p><br></p>") == ""
    assert get_plain_text("<b>isi</b>") == "isi"