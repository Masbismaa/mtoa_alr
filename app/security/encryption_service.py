"""Enkripsi & dekripsi access note pake Fernet."""

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

from app.utils.exceptions import InvalidCredentialError


@lru_cache(maxsize=4)
def build_fernet(encryption_key):
    """Bikin objek Fernet dari key. Di-cache, jadi cukup dibikin sekali per key."""
    try:
        return Fernet(encryption_key)
    except (ValueError, TypeError) as error:
        # key salah format, mending ketahuan dari awal pas app start
        raise RuntimeError(
            "ENCRYPTION_KEY ga valid. Generate ulang pake Fernet.generate_key()"
        ) from error


def get_fernet():
    """Ambil objek Fernet sesuai ENCRYPTION_KEY di config yg lagi aktif."""
    return build_fernet(current_app.config["ENCRYPTION_KEY"])


def encrypt_credential(plain_text):
    """Enkripsi teks jadi token; input kosong -> None."""
    if plain_text is None or plain_text == "":
        return None
    return get_fernet().encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_credential(encrypted_text):
    """Buka token encrypt_credential; token rusak / key beda -> InvalidCredentialError."""
    if not encrypted_text:
        return None
    try:
        return get_fernet().decrypt(encrypted_text.encode("utf-8")).decode("utf-8")
    except InvalidToken as error:
        raise InvalidCredentialError("Kredensial ga bisa dibuka, datanya rusak atau key beda") from error