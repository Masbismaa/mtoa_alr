"""Pengiriman email (OTP login, kode verifikasi daftar, pemberitahuan) sesuai mode yang dikonfigurasi."""

import smtplib
import ssl
from email.message import EmailMessage
from flask import current_app

from app.utils.constants import (
    OTP_DELIVERY_CONSOLE, OTP_DELIVERY_SMTP, OTP_EXPIRE_MINUTES,
    OTP_PURPOSE_LOGIN, OTP_PURPOSE_REGISTER, OTP_PURPOSE_RESET,
)

# judul email per tujuan OTP (kodenya sama-sama dari tabel otp_codes)
OTP_SUBJECT_DICT = {
    OTP_PURPOSE_LOGIN: "ALR login code",
    OTP_PURPOSE_REGISTER: "ALR registration verification code",
    OTP_PURPOSE_RESET: "ALR password reset code",
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

    if delivery_mode != OTP_DELIVERY_SMTP:
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
    send_email(user.email, subject, f"{subject}: {otp_code}\nValid for {OTP_EXPIRE_MINUTES} minutes. Do not share this code.")

def send_registration_notice(user):
    """Ada yg nyoba daftar pakai email yg udah punya akun. Pemiliknya dikabarin lewat email (bukan lewat layar,
    biar orang lain ga bisa ngecek email mana yg udah terdaftar)."""
    send_email(
        user.email,
        "ALR registration attempt",
        "Someone tried to register on ALR with this email, but you already have an account.\n"
        "If that was you, just log in. If not, ignore this email; your account has not changed.",
    )

def send_password_changed_notice(user):
    """Password akun baru aja diganti (lewat Settings / lupa password). Biar pemilik sadar kalau itu bukan dia."""
    send_email(
        user.email,
        "ALR password changed",
        "The password for your ALR account was just changed, and all other sessions were logged out.\n"
        "If this wasn't you, contact the ICT admin right away.",
    )
