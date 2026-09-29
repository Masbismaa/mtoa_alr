"""Test pembuatan & pengecekan OTP."""
from app.security.otp_service import generate_otp_code, hash_otp_code, is_otp_code_match

def test_generate_otp_code_is_six_digits():
    """Positive: OTP selalu 6 digit angka (termasuk yg depannya 0)."""
    for _ in range(50):
        otp_code = generate_otp_code()
        assert len(otp_code) == 6
        assert otp_code.isdigit()

def test_otp_hash_matches_original_code(app):
    """Positive: hash bukan angka asli, tapi bisa dicocokin."""
    code_hash = hash_otp_code("123456")
    assert "123456" not in code_hash
    assert is_otp_code_match("123456", code_hash) is True

def test_otp_hash_rejects_wrong_or_empty_code(app):
    """Negative: kode salah / kosong ditolak."""
    code_hash = hash_otp_code("123456")
    assert is_otp_code_match("654321", code_hash) is False
    assert is_otp_code_match("", code_hash) is False
    assert is_otp_code_match("123456", None) is False