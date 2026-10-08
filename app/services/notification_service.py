"""Pengiriman email (OTP login, kode verifikasi daftar, pemberitahuan) sesuai mode yang dikonfigurasi."""

import smtplib
import ssl
from email.message import EmailMessage
from flask import current_app

from app.utils.constants import OTP_DELIVERY_CONSOLE, OTP_EXPIRE_MINUTES, OTP_PURPOSE_LOGIN, OTP_PURPOSE_REGISTER

# judul email per tujuan OTP (kodenya sama-sama dari tabel otp_codes)
OTP_SUBJECT_DICT = {
    OTP_PURPOSE_LOGIN: "Kode login ALR",
    OTP_PURPOSE_REGISTER: "Kode verifikasi pendaftaran ALR",
}

def send_email(to_address, subject, body):
    """Kirim satu email sesuai OTP_DELIVERY_MODE.

    console -> dicetak ke terminal (khusus ujicoba).
    smtp    -> SMTP dengan STARTTLS atau TLS langsung, sertifikat selalu diverifikasi.
    """
    delivery_mode = current_app.config["OTP_DELIVERY_MODE"]

    if delivery_mode == OTP_DELIVERY_CONSOLE:
        # Mode development: email ditulis ke terminal.
        print(f"\n===== [DEV] Email ke {to_address}: {subject} =====\n{body}\n=====\n", flush=True)
        return

    if delivery_mode != "smtp":
        raise RuntimeError("Mode pengiriman OTP tidak dikenal")
    config = current_app.config
    if not config["SMTP_HOST"] or not config["SMTP_FROM"]:
        raise RuntimeError("SMTP_HOST dan SMTP_FROM wajib diisi")
    message = EmailMessage()
    message["From"] = config["SMTP_FROM"]
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)
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

def send_otp_code(user, otp_code, purpose=OTP_PURPOSE_LOGIN):
    """Kirim kode OTP (login / verifikasi pendaftaran). `user` = User atau PendingRegistration, yg dipake cuma .email."""
    subject = OTP_SUBJECT_DICT[purpose]
    send_email(user.email, subject, f"{subject}: {otp_code}\nBerlaku {OTP_EXPIRE_MINUTES} menit. Jangan bagikan kode ini.")

def send_registration_notice(user):
    """Ada yg nyoba daftar pakai email yg udah punya akun. Pemiliknya dikabarin lewat email (bukan lewat layar,
    biar orang lain ga bisa ngecek email mana yg udah terdaftar)."""
    send_email(
        user.email,
        "Percobaan pendaftaran ALR",
        "Ada yang mencoba mendaftar di ALR memakai email ini, padahal kamu sudah punya akun.\n"
        "Kalau itu kamu, langsung login saja. Kalau bukan, abaikan email ini; akunmu tidak berubah.",
    )
