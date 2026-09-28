"""Kirim notifikasi ke user. Sekarang baru OTP, lewat terminal dulu."""

from flask import current_app

from app.utils.constants import OTP_DELIVERY_CONSOLE, OTP_EXPIRE_MINUTES

def send_otp_code(user, otp_code):
    """Kirim OTP ke user sesuai OTP_DELIVERY_MODE.

    console -> dicetak ke terminal (khusus ujicoba).
    smtp    -> belum dibikin, nyusul kalau info SMTP Intramail udah ada.
    """
    delivery_mode = current_app.config["OTP_DELIVERY_MODE"]

    if delivery_mode == OTP_DELIVERY_CONSOLE:
        # aku kasih dekorasi biar mencolok + gampang dicari di terminal
        print(
            f"\n===== [DEV] OTP untuk {user.email}: {otp_code} "
            f"(berlaku {OTP_EXPIRE_MINUTES} menit) =====\n",
            flush=True,
        )
        return

    raise RuntimeError(f"Mode kirim OTP '{delivery_mode}' belum disetup")