"""Bikin & cek kode OTP. Yg disimpen di DB cuma hash-nya, bukan angka aslinya."""
import hashlib
import hmac
import secrets

from flask import current_app

from app.utils.constants import OTP_LENGTH

def generate_otp_code():
    """Bikin OTP angka acak (default 6 digit) pake generator yg aman buat kriptografi."""
    return f"{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}"

def hash_otp_code(otp_code):
    """Hash OTP pake HMAC-SHA256 + SECRET_KEY. Kalau DB bocor, OTP-nya insyaalah ga kebaca."""
    secret_bytes = current_app.config["SECRET_KEY"].encode("utf-8")
    return hmac.new(secret_bytes, otp_code.encode("utf-8"), hashlib.sha256).hexdigest()

def is_otp_code_match(otp_code, code_hash):
    """Cek OTP yg diketik cocok sama hash di DB. compare_digest biar aman dari timing attack."""
    if not otp_code or not code_hash:
        return False
    return hmac.compare_digest(hash_otp_code(otp_code), code_hash)