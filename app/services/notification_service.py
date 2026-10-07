"""Pengiriman OTP sesuai mode notifikasi yang dikonfigurasi."""

import smtplib
import ssl
from email.message import EmailMessage
from flask import current_app

from app.utils.constants import OTP_DELIVERY_CONSOLE, OTP_EXPIRE_MINUTES

def send_otp_code(user, otp_code):
    """Kirim OTP ke user sesuai OTP_DELIVERY_MODE.

    console -> dicetak ke terminal (khusus ujicoba).
    smtp    -> SMTP dengan STARTTLS atau TLS langsung, sertifikat selalu diverifikasi.
    """
    delivery_mode = current_app.config["OTP_DELIVERY_MODE"]

    if delivery_mode == OTP_DELIVERY_CONSOLE:
        # Mode development: OTP ditulis ke terminal.
        print(
            f"\n===== [DEV] OTP untuk {user.email}: {otp_code} "
            f"(berlaku {OTP_EXPIRE_MINUTES} menit) =====\n",
            flush=True,
        )
        return

    if delivery_mode != "smtp":
        raise RuntimeError("Mode pengiriman OTP tidak dikenal")
    config = current_app.config
    if not config["SMTP_HOST"] or not config["SMTP_FROM"]:
        raise RuntimeError("SMTP_HOST dan SMTP_FROM wajib diisi")
    message = EmailMessage()
    message["From"] = config["SMTP_FROM"]
    message["To"] = user.email
    message["Subject"] = "Kode login ALR"
    message.set_content(f"Kode login ALR: {otp_code}\nBerlaku {OTP_EXPIRE_MINUTES} menit. Jangan bagikan kode ini.")
    security = config["SMTP_SECURITY"]
    if security not in ("starttls", "ssl"):
        raise RuntimeError("SMTP_SECURITY harus starttls atau ssl")
    context = ssl.create_default_context()
    connection_type = smtplib.SMTP_SSL if security == "ssl" else smtplib.SMTP
    option_dict = {"timeout": config["SMTP_TIMEOUT_SECONDS"]}
    if security == "ssl":
        option_dict["context"] = context
    with connection_type(config["SMTP_HOST"], config["SMTP_PORT"], **option_dict) as connection:
        if security == "starttls":
            connection.ehlo()
            connection.starttls(context=context)
            connection.ehlo()
        if config["SMTP_USERNAME"]:
            connection.login(config["SMTP_USERNAME"], config["SMTP_PASSWORD"])
        connection.send_message(message)
