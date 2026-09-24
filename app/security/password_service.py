"""Hash & cek password login pake Argon2id (satu arah, ga bisa dibalikin)."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.utils.constants import MIN_PASSWORD_LENGTH

# cukup satu hasher buat seluruh app, parameter default argon2 udah aman
_password_hasher = PasswordHasher()

def hash_password(plain_password):
    """Ubah password jadi hash Argon2 buat disimpen ke DB."""
    # tolak password kosong / kependekan dari awal
    if not plain_password or len(plain_password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password minimal {MIN_PASSWORD_LENGTH} karakter")
    return _password_hasher.hash(plain_password)

def verify_password(password_hash, plain_password):
    """Cek password yg diketik user cocok ga sama hash di DB. Return True/False aja."""
    if not password_hash or not plain_password:
        return False
    try:
        return _password_hasher.verify(password_hash, plain_password)
    except (VerificationError, InvalidHashError):
        # password salah atau hash-nya rusak, dua-duanya dianggap gagal
        return False

def is_rehash_needed(password_hash):
    """Cek hash lama perlu dibikin ulang ga (misal parameter argon2 dinaikin)."""
    return _password_hasher.check_needs_rehash(password_hash)