"""Pembuatan dan verifikasi OTP; database hanya menyimpan hash OTP."""
import hashlib
import hmac
import secrets

from flask import current_app

from app.utils.constants import OTP_LENGTH

def generate_otp_code():
    """Menghasilkan OTP numerik dengan generator acak kriptografis."""
    return f"{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}"

def hash_otp_code(otp_code):
    """Menghasilkan HMAC-SHA256 OTP dengan SECRET_KEY."""
    secret_bytes = current_app.config["SECRET_KEY"].encode("utf-8")
    return hmac.new(secret_bytes, otp_code.encode("utf-8"), hashlib.sha256).hexdigest()

def is_otp_code_match(otp_code, code_hash):
    """Memverifikasi OTP dengan perbandingan waktu-konstan."""
    if not otp_code or not code_hash:
        return False
    return hmac.compare_digest(hash_otp_code(otp_code), code_hash)
