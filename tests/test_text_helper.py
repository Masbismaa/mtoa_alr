"""Test helper teks (email, inisial, label role/visibilitas/status)."""
from app.utils.text_helper import (
    get_initials,
    get_link_status_label,
    get_role_label,
    get_visibility_label,
    mask_email,
    normalize_email,
)

def test_normalize_email_trims_and_lowercases():
    """Positive: spasi dibuang, huruf jadi kecil."""
    assert normalize_email("  User.Login@Spindo.COM ") == "user.login@spindo.com"

def test_normalize_email_none_returns_empty_string():
    """Negative: None ga bikin error."""
    assert normalize_email(None) == ""

def test_mask_email_hides_local_part():
    """Positive: cuma 2 huruf depan yg keliatan."""
    assert mask_email("user.login@spindo.com") == "us********@spindo.com"
    assert mask_email("a@spindo.com") == "a*@spindo.com"

def test_get_initials_takes_first_three_words():
    """Positive (revisi): ambil huruf depan maks 3 kata, huruf besar."""
    assert get_initials("Mochammad Bisma Prasetya") == "MBP"
    assert get_initials("mochammad bisma prasetya putra") == "MBP"

def test_get_initials_short_name():
    """Positive: nama 1-2 kata tetep jalan."""
    assert get_initials("Bisma Prasetya") == "BP"
    assert get_initials("Bisma") == "B"

def test_get_initials_empty_name():
    """Negative: nama kosong jadi tanda tanya, bukan error."""
    assert get_initials("   ") == "?"

def test_get_role_label():
    """Positive: kode role diubah jadi label, role asing tetep tampil apa adanya."""
    assert get_role_label("user_entry") == "User Entry"
    assert get_role_label("admin") == "Admin"
    assert get_role_label("lainnya") == "lainnya"

def test_get_visibility_and_link_status_label():
    """Positive: label visibilitas & status link."""
    assert get_visibility_label("public") == "Public"
    assert get_visibility_label("private") == "Private"
    assert get_link_status_label("unknown") == "Belum dicek"