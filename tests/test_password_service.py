"""Test hash & verifikasi password login."""
import pytest

from app.security.password_service import hash_password, is_rehash_needed, verify_password

def test_hash_password_and_verify_success():
    """hash bukan password asli, dan password yg bener lolos verifikasi."""
    password_hash = hash_password("PasswordKuat123")
    assert password_hash != "PasswordKuat123"
    assert password_hash.startswith("$argon2id$")
    assert verify_password(password_hash, "PasswordKuat123") is True

def test_verify_wrong_password_returns_false():
    """password salah harus False, bukan error."""
    password_hash = hash_password("PasswordKuat123")
    assert verify_password(password_hash, "PasswordSalah") is False

def test_verify_with_broken_hash_returns_false():
    """hash rusak / kosong dianggap gagal, bukan bikin app crash."""
    assert verify_password("bukan-hash-argon", "PasswordKuat123") is False
    assert verify_password(None, "PasswordKuat123") is False

def test_hash_short_password_raises_error():
    """password kependekan ditolak."""
    with pytest.raises(ValueError):
        hash_password("123")

def test_fresh_hash_does_not_need_rehash():
    """hash yg baru dibikin ga perlu di-hash ulang."""
    assert is_rehash_needed(hash_password("PasswordKuat123")) is False