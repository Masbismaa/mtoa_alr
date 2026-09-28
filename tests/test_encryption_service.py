"""Test enkripsi & dekripsi kredensial."""

import pytest
from cryptography.fernet import Fernet

from app.security.encryption_service import decrypt_credential, encrypt_credential
from app.utils.exceptions import InvalidCredentialError

def test_encrypt_then_decrypt_returns_original(app):
    """hasil enkripsi bisa dibuka lagi jadi teks asli."""
    encrypted_text = encrypt_credential("P@ssw0rd-Router!")
    assert decrypt_credential(encrypted_text) == "P@ssw0rd-Router!"

def test_encrypted_text_is_not_plain_and_random(app):
    """hasil enkripsi ga boleh sama kayak aslinya, dan beda tiap kali dienkripsi."""
    first_text = encrypt_credential("rahasia123")
    second_text = encrypt_credential("rahasia123")
    assert "rahasia123" not in first_text
    assert first_text != second_text

def test_encrypt_empty_value_returns_none(app):
    """input kosong disimpen sebagai None (NULL)."""
    assert encrypt_credential("") is None
    assert encrypt_credential(None) is None
    assert decrypt_credential(None) is None

def test_decrypt_tampered_text_raises_error(app):
    """token yg diutak-atik harus ditolak."""
    encrypted_text = encrypt_credential("rahasia123")
    tampered_text = encrypted_text[:-5] + "AAAAA"
    with pytest.raises(InvalidCredentialError):
        decrypt_credential(tampered_text)

def test_decrypt_with_different_key_raises_error(app):
    """data ga bisa dibuka pake key lain."""
    encrypted_text = encrypt_credential("rahasia123")
    app.config["ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    with pytest.raises(InvalidCredentialError):
        decrypt_credential(encrypted_text)