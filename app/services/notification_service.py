"""Pengiriman email (OTP login, kode lupa password, link aktivasi akun, pemberitahuan) sesuai mode yang dikonfigurasi."""

import hashlib
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from flask import current_app

from app.utils.constants import (
    ACTIVATION_LINK_EXPIRE_HOURS, OTP_DELIVERY_CONSOLE, OTP_EXPIRE_MINUTES, OTP_PURPOSE_LOGIN, OTP_PURPOSE_RESET,
)

# judul email per tujuan OTP (kodenya sama-sama dari tabel otp_codes)
OTP_SUBJECT_DICT = {
    OTP_PURPOSE_LOGIN: "Kode login ALR",
    OTP_PURPOSE_RESET: "Kode reset password ALR",
}
SIGNATURE_TEXT = "Best Regards,\nICT SPINDO"

def send_email(to_address, subject, paragraph_list, code=None, link=None, link_label=None, note_list=()):
    """Kirim satu email (teks biasa + HTML dgn tanda tangan ICT SPINDO) sesuai OTP_DELIVERY_MODE.

    console -> dicetak ke terminal (khusus ujicoba).
    smtp    -> SMTP dengan STARTTLS atau TLS langsung, sertifikat selalu diverifikasi.
    """
    delivery_mode = current_app.config["OTP_DELIVERY_MODE"]
    text_part_list = [*paragraph_list, *([code] if code else []), *([link] if link else []), *note_list, SIGNATURE_TEXT]
    body = "\n\n".join(text_part_list)

    if delivery_mode == OTP_DELIVERY_CONSOLE:
        print(f"\n===== [DEV] Email ke {to_address}: {subject} =====\n{body}\n=====\n", flush=True)
        return

    # mode & SMTP_HOST/SMTP_FROM udah dicek pas aplikasi nyala (create_app)
    config = current_app.config
    message = EmailMessage()
    message["From"] = config["SMTP_FROM"]
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)
    # jinja_env langsung (bukan render_template): context processor halaman butuh request & user login
    message.add_alternative(current_app.jinja_env.get_template("emails/notification.html").render(
        subject=subject, paragraph_list=paragraph_list, code=code,
        link=link, link_label=link_label, note_list=note_list,
    ), subtype="html")
    # logo ditempel di email (cid), bukan link ke server: klien email sering blokir gambar dari luar
    logo_bytes = (Path(current_app.static_folder) / "images" / "spindo_logo.png").read_bytes()
    message.get_payload()[1].add_related(logo_bytes, "image", "png", cid="<spindo-logo>")
    security = config["SMTP_SECURITY"]
    if security not in ("starttls", "ssl"):
        raise RuntimeError("SMTP_SECURITY harus starttls atau ssl")
    pinned_sha256 = config["SMTP_CERT_SHA256"]
    context = ssl.create_default_context()
    if pinned_sha256:
        # sertifikat self-signed: cek CA & nama diganti cek sidik jari persis, sebelum password dikirim
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    connection_type = smtplib.SMTP_SSL if security == "ssl" else smtplib.SMTP
    option_dict = {"timeout": config["SMTP_TIMEOUT_SECONDS"]}
    if security == "ssl":
        option_dict["context"] = context
    with connection_type(config["SMTP_HOST"], config["SMTP_PORT"], **option_dict) as connection:
        if security == "starttls":
            connection.ehlo()
            connection.starttls(context=context)
            connection.ehlo()
        if pinned_sha256:
            peer_cert = connection.sock.getpeercert(binary_form=True) or b""
            if hashlib.sha256(peer_cert).hexdigest() != pinned_sha256:
                raise ssl.SSLError("Sidik jari sertifikat SMTP tidak cocok dengan SMTP_CERT_SHA256")
        if config["SMTP_USERNAME"]:
            connection.login(config["SMTP_USERNAME"], config["SMTP_PASSWORD"])
        connection.send_message(message)

def send_otp_code(user, otp_code, purpose=OTP_PURPOSE_LOGIN):
    """Kirim kode OTP login / lupa password ke email user."""
    send_email(
        user.email, OTP_SUBJECT_DICT[purpose],
        [f"Halo {user.full_name},", "Gunakan kode berikut untuk melanjutkan di ALR:"],
        code=otp_code,
        note_list=[f"Kode berlaku {OTP_EXPIRE_MINUTES} menit. Jangan berikan kode ini kepada siapa pun, termasuk tim ICT."],
    )

def send_activation_link(user, activation_url):
    """Link aktivasi akun baru yg dibikin admin. Pemilik email bikin password sendiri lewat link ini."""
    send_email(
        user.email, "Aktivasi akun ALR Anda",
        [f"Halo {user.full_name},",
         f"Admin ICT telah membuatkan akun ALR untuk {user.email}. "
         "Klik tombol di bawah untuk membuat password dan mengaktifkan akun Anda."],
        link=activation_url, link_label="Aktifkan Akun",
        note_list=[f"Link berlaku {ACTIVATION_LINK_EXPIRE_HOURS} jam dan hanya bisa dipakai satu kali.",
                   "Kalau Anda tidak merasa meminta akun ini, abaikan email ini."],
    )

def send_password_changed_notice(user):
    """Password akun baru aja diganti (lewat Settings / lupa password). Biar pemilik sadar kalau itu bukan dia."""
    send_email(
        user.email, "Password ALR Anda telah diganti",
        [f"Halo {user.full_name},",
         "Password akun ALR Anda baru saja diganti, dan semua sesi login lain sudah dikeluarkan."],
        note_list=["Kalau ini bukan Anda, segera hubungi Admin ICT."],
    )
