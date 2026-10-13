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
    DataRequired(message="Email is required"),
    Length(max=255, message="Email is too long"),
    Regexp(EMAIL_PATTERN, message="Invalid email format"),
]

# aturan password baru dipake bareng: daftar, lupa password, ganti password
NEW_PASSWORD_VALIDATOR_LIST = [
    DataRequired(message="Password is required"),
    Length(min=MIN_PASSWORD_LENGTH, max=MAX_PASSWORD_LENGTH,
           message=f"Password must be {MIN_PASSWORD_LENGTH}-{MAX_PASSWORD_LENGTH} characters"),
    Regexp(PASSWORD_PATTERN, message="Password must contain letters and numbers"),
]
CONFIRM_PASSWORD_VALIDATOR_LIST = [
    DataRequired(message="Password confirmation is required"),
    EqualTo("password", message="Passwords do not match"),
]
FULL_NAME_VALIDATOR_LIST = [DataRequired(message="Name is required"), Length(max=150)]
DEPARTMENT_VALIDATOR_LIST = [DataRequired(message="Department is required"), Length(max=100)]
JOB_TITLE_VALIDATOR_LIST = [DataRequired(message="Job title is required"), Length(max=100)]
OTP_VALIDATOR_LIST = [
    DataRequired(message="OTP code is required"),
    Regexp(OTP_PATTERN, message=f"OTP code must be {OTP_LENGTH} digits"),
]


class LoginForm(FlaskForm):
    """Login langkah 1: email + password."""
    email = EmailField("Email", validators=EMAIL_VALIDATOR_LIST, filters=[complete_corporate_email])
    password = PasswordField("Password", validators=[
        DataRequired(message="Password is required"),
        Length(max=MAX_PASSWORD_LENGTH, message="Password is too long"),
    ])
    submit = SubmitField("Next")


class RegisterForm(FlaskForm):
    """Daftar akun baru (role otomatis User Entry)."""
    email = EmailField("Corporate Email", validators=EMAIL_VALIDATOR_LIST, filters=[complete_corporate_email])
    full_name = StringField("Full Name", validators=FULL_NAME_VALIDATOR_LIST)
    department = StringField("Department", validators=DEPARTMENT_VALIDATOR_LIST)
    job_title = StringField("Job Title", validators=JOB_TITLE_VALIDATOR_LIST)
    password = PasswordField("Password", validators=NEW_PASSWORD_VALIDATOR_LIST)
    confirm_password = PasswordField("Confirm Password", validators=CONFIRM_PASSWORD_VALIDATOR_LIST)
    submit = SubmitField("Register")


class OtpForm(FlaskForm):
    """Login langkah 2: isi kode OTP."""
    otp_code = StringField("OTP Code", validators=OTP_VALIDATOR_LIST)
    submit = SubmitField("Verify")


class ForgotPasswordForm(FlaskForm):
    """Lupa password langkah 1: email."""
    email = EmailField("Corporate Email", validators=EMAIL_VALIDATOR_LIST, filters=[complete_corporate_email])
    submit = SubmitField("Send Code")


class ResetPasswordForm(FlaskForm):
    """Lupa password langkah 2: kode dari email + password baru."""
    otp_code = StringField("Code", validators=OTP_VALIDATOR_LIST)
    password = PasswordField("New Password", validators=NEW_PASSWORD_VALIDATOR_LIST)
    confirm_password = PasswordField("Confirm New Password", validators=CONFIRM_PASSWORD_VALIDATOR_LIST)
    submit = SubmitField("Reset Password")


class ChangePasswordForm(FlaskForm):
    """Ganti password dari Settings: password lama + baru."""
    current_password = PasswordField("Current Password", validators=[
        DataRequired(message="Current password is required"),
        Length(max=MAX_PASSWORD_LENGTH, message="Password is too long"),
    ])
    password = PasswordField("New Password", validators=NEW_PASSWORD_VALIDATOR_LIST)
    confirm_password = PasswordField("Confirm New Password", validators=CONFIRM_PASSWORD_VALIDATOR_LIST)
    submit = SubmitField("Change Password")

class ProfileForm(FlaskForm):
    """Edit profil sendiri di Settings (email & role ga ikut)."""
    full_name = StringField("Full Name", validators=FULL_NAME_VALIDATOR_LIST)
    department = StringField("Department", validators=DEPARTMENT_VALIDATOR_LIST)
    job_title = StringField("Job Title", validators=JOB_TITLE_VALIDATOR_LIST)
    submit = SubmitField("Save Profile")
