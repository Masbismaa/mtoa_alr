"""Test helper teks (normalisasi & masking email)."""
from app.utils.text_helper import mask_email, normalize_email

def test_normalize_email_trims_and_lowercases():
    """Spasi dibuang, huruf jadi kecil."""
    assert normalize_email("  User.Login@Spindo.COM ") == "user.login@spindo.com"

def test_normalize_email_none_returns_empty_string():
    """None ga bikin error."""
    assert normalize_email(None) == ""

def test_mask_email_hides_local_part():
    """Cuma 2 huruf depan yg keliatan."""
    assert mask_email("user.login@spindo.com") == "us********@spindo.com"
    assert mask_email("a@spindo.com") == "a*@spindo.com"