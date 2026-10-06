"""Form login, register, dan OTP. Validasi dasar di sini, aturan bisnis di auth_service."""
from flask import current_app
from flask_wtf import FlaskForm
from wtforms import EmailField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Regexp

from app.utils.constants import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH, OTP_LENGTH
from app.utils.text_helper import complete_email

# pola email sederhana, cek domain-nya di service
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
# minimal ada huruf dan angka
PASSWORD_PATTERN = r"^(?=.*[A-Za-z])(?=.*\d).+$"
OTP_PATTERN = rf"^\d{{{OTP_LENGTH}}}$"

def complete_corporate_email(value):
    """Filter form: user cukup isi nama depan email, domain kantor ditambahin otomatis sebelum divalidasi."""
    return complete_email(value, current_app.config["ALLOWED_EMAIL_DOMAIN"])

# validator email dipake di 2 form, jadi dikumpulin sekali aja
EMAIL_VALIDATOR_LIST = [
    DataRequired(message="Email wajib diisi"),
    Length(max=255, message="Email kepanjangan"),
    Regexp(EMAIL_PATTERN, message="Format email tidak valid"),
]


class LoginForm(FlaskForm):
    """Login langkah 1: email + password."""
    email = EmailField("Email", validators=EMAIL_VALIDATOR_LIST, filters=[complete_corporate_email])
    password = PasswordField("Password", validators=[
        DataRequired(message="Password wajib diisi"),
        Length(max=MAX_PASSWORD_LENGTH, message="Password kepanjangan"),
    ])
    submit = SubmitField("Next")


class RegisterForm(FlaskForm):
    """Daftar akun baru (role otomatis User Entry)."""
    email = EmailField("Email Korporat", validators=EMAIL_VALIDATOR_LIST, filters=[complete_corporate_email])
    full_name = StringField("Nama Lengkap", validators=[DataRequired(message="Nama wajib diisi"), Length(max=150)])
    department = StringField("Departemen", validators=[DataRequired(message="Departemen wajib diisi"), Length(max=100)])
    job_title = StringField("Jabatan", validators=[DataRequired(message="Jabatan wajib diisi"), Length(max=100)])
    password = PasswordField("Password", validators=[
        DataRequired(message="Password wajib diisi"),
        Length(min=MIN_PASSWORD_LENGTH, max=MAX_PASSWORD_LENGTH,
               message=f"Password {MIN_PASSWORD_LENGTH}-{MAX_PASSWORD_LENGTH} karakter"),
        Regexp(PASSWORD_PATTERN, message="Password wajib berisi huruf dan angka"),
    ])
    confirm_password = PasswordField("Konfirmasi Password", validators=[
        DataRequired(message="Konfirmasi password wajib diisi"),
        EqualTo("password", message="Konfirmasi password tidak sama"),
    ])
    submit = SubmitField("Daftar")


class OtpForm(FlaskForm):
    """Login langkah 2: isi kode OTP."""
    otp_code = StringField("Kode OTP", validators=[
        DataRequired(message="Kode OTP wajib diisi"),
        Regexp(OTP_PATTERN, message=f"Kode OTP harus {OTP_LENGTH} digit angka"),
    ])
    submit = SubmitField("Verifikasi")