"""Route register, login 2 langkah (password -> OTP), kirim ulang OTP, lupa password, dan logout."""
from flask import Blueprint, flash, redirect, render_template, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db, limiter
from app.models import User
from app.schemas.auth_schema import ForgotPasswordForm, LoginForm, OtpForm, RegisterForm, ResetPasswordForm
from app.services.audit_service import log_audit
from app.services.auth_service import (
    RegistrationFinishedError,
    authenticate_user,
    can_continue_login,
    resend_otp_challenge,
    resend_password_reset_code,
    resend_registration_code,
    reset_password as reset_password_with_code,
    start_otp_challenge,
    start_password_reset,
    start_registration,
    verify_otp_code,
    verify_registration,
)
from app.utils.constants import (
    AUDIT_ACTION_LOGOUT,
    OTP_LENGTH,
    OTP_RESEND_COOLDOWN_SECONDS,
    SESSION_PASSWORD_RESET_KEY,
    SESSION_PENDING_REGISTER_KEY,
    SESSION_PENDING_USER_KEY,
)
from app.utils.exceptions import AuthError
from app.utils.text_helper import mask_email

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

def get_pending_user():
    """Ambil user yg udah lolos password tapi belum isi OTP."""
    pending_user_id = session.get(SESSION_PENDING_USER_KEY)
    if not pending_user_id:
        return None
    return db.session.get(User, pending_user_id)

def end_pending_login(message):
    session.pop(SESSION_PENDING_USER_KEY, None)
    flash(message, "danger")
    return redirect(url_for("auth.login"))

@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def register():
    """Halaman daftar akun."""
    # udah login ngapain daftar lagi
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    form = RegisterForm()
    if form.validate_on_submit():
        try:
            registration_state = start_registration(
                email=form.email.data,
                password=form.password.data,
                full_name=form.full_name.data,
                department=form.department.data,
                job_title=form.job_title.data,
            )
        except AuthError as error:
            flash(str(error), "danger")
        else:
            # email baru maupun yg udah terdaftar sampe sini dgn tampilan yg sama (lihat start_registration)
            session[SESSION_PENDING_REGISTER_KEY] = registration_state
            flash("Check your email to continue registration", "info")
            return redirect(url_for("auth.verify_register"))

    return render_template("pages/auth/register.html", form=form)

def get_registration_state():
    """Data pendaftaran yg nunggu kode verifikasi, None kalau belum daftar / udah selesai."""
    state = session.get(SESSION_PENDING_REGISTER_KEY)
    # format lengkap aja yg diterima (session dari versi lama tanpa token dianggap habis -> daftar ulang)
    is_valid = isinstance(state, dict) and all(state.get(key) is not None for key in ("email", "token", "sent_at", "attempt_count"))
    return state if is_valid else None

def end_registration_session(message, category):
    session.pop(SESSION_PENDING_REGISTER_KEY, None)
    flash(message, category)

@auth_bp.route("/register/verify", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def verify_register():
    """Daftar langkah 2: masukin kode verifikasi yg dikirim ke email."""
    registration_state = get_registration_state()
    if registration_state is None:
        flash("Your registration session expired, please register again", "warning")
        return redirect(url_for("auth.register"))

    form = OtpForm()
    if form.validate_on_submit():
        try:
            verify_registration(registration_state, form.otp_code.data)
        except RegistrationFinishedError as error:
            # email ini keburu jadi akun lewat percobaan daftar lain (yg juga pegang kode dari email itu)
            end_registration_session(str(error), "info")
            return redirect(url_for("auth.login"))
        except AuthError as error:
            flash(str(error), "danger")
        else:
            end_registration_session("Email verified, your account is active. Please log in.", "success")
            return redirect(url_for("auth.login"))
        finally:
            # hitungan percobaan bisa berubah (cabang email udah terdaftar), disimpen balik ke session
            if get_registration_state() is not None:
                session[SESSION_PENDING_REGISTER_KEY] = registration_state

    return render_template(
        "pages/auth/register_verify.html",
        form=form,
        masked_email=mask_email(registration_state["email"]),
        otp_length=OTP_LENGTH,
        resend_cooldown_seconds=OTP_RESEND_COOLDOWN_SECONDS,
    )

@auth_bp.post("/register/resend")
@limiter.limit("3 per minute")
def resend_register_code():
    """Kirim ulang kode verifikasi daftar."""
    registration_state = get_registration_state()
    if registration_state is None:
        flash("Your registration session expired, please register again", "warning")
        return redirect(url_for("auth.register"))
    try:
        resend_registration_code(registration_state)
    except AuthError as error:
        flash(str(error), "warning")
    else:
        session[SESSION_PENDING_REGISTER_KEY] = registration_state
        flash("A new verification code has been sent", "success")
    return redirect(url_for("auth.verify_register"))

@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    """Login langkah 1: email + password, abis itu lanjut ke halaman OTP."""
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = authenticate_user(form.email.data, form.password.data)
            start_otp_challenge(user)
        except AuthError as error:
            flash(str(error), "danger")
        else:
            # session dibersihin dulu, terus simpen user yg lagi nunggu OTP
            session.clear()
            session[SESSION_PENDING_USER_KEY] = user.id
            return redirect(url_for("auth.verify_otp"))

    return render_template("pages/auth/login.html", form=form)

@auth_bp.route("/otp", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def verify_otp():
    """Login langkah 2: isi OTP."""
    pending_user = get_pending_user()
    # belum lewat langkah 1 -> balikin ke login
    if pending_user is None:
        flash("Your login session expired, please log in again", "warning")
        return redirect(url_for("auth.login"))

    form = OtpForm()
    if form.validate_on_submit():
        try:
            verify_otp_code(pending_user, form.otp_code.data)
        except AuthError as error:
            if not can_continue_login(pending_user):
                return end_pending_login(str(error))
            flash(str(error), "danger")
        else:
            # ganti ke session baru yg bersih, baru login-in user
            session.clear()
            login_user(pending_user)
            session.permanent = True
            return redirect(url_for("main.home"))

    return render_template(
        "pages/auth/otp.html",
        form=form,
        masked_email=mask_email(pending_user.email),
        otp_length=OTP_LENGTH,
        resend_cooldown_seconds=OTP_RESEND_COOLDOWN_SECONDS,
    )

@auth_bp.post("/otp/resend")
@limiter.limit("3 per minute")
def resend_otp():
    """Kirim ulang OTP (CSRF dicek otomatis sama CSRFProtect)."""
    pending_user = get_pending_user()
    if pending_user is None:
        flash("Your login session expired, please log in again", "warning")
        return redirect(url_for("auth.login"))

    try:
        resend_otp_challenge(pending_user)
    except AuthError as error:
        if not can_continue_login(pending_user):
            return end_pending_login(str(error))
        flash(str(error), "warning")
    else:
        flash("A new OTP has been sent", "success")
    return redirect(url_for("auth.verify_otp"))

# LUPA PASSWORD
def get_password_reset_state():
    return session.get(SESSION_PASSWORD_RESET_KEY)

def expired_password_reset():
    flash("Your password reset session expired, please request a new code", "warning")
    return redirect(url_for("auth.forgot_password"))

@auth_bp.route("/forgot", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def forgot_password():
    """Lupa password langkah 1: isi email. Layar selalu sama, terdaftar atau nggak."""
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        try:
            reset_state = start_password_reset(form.email.data)
        except AuthError as error:
            flash(str(error), "danger")
        else:
            session[SESSION_PASSWORD_RESET_KEY] = reset_state
            flash("If the email is registered, a reset code has been sent", "info")
            return redirect(url_for("auth.reset_password"))
    return render_template("pages/auth/forgot.html", form=form)

@auth_bp.route("/reset", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def reset_password():
    """Lupa password langkah 2: kode dari email + password baru."""
    reset_state = get_password_reset_state()
    if reset_state is None:
        return expired_password_reset()

    form = ResetPasswordForm()
    if form.validate_on_submit():
        try:
            reset_password_with_code(reset_state, form.otp_code.data, form.password.data)
        except AuthError as error:
            flash(str(error), "danger")
            # hitungan percobaan cabang email ga terdaftar disimpen balik ke session
            session[SESSION_PASSWORD_RESET_KEY] = reset_state
        else:
            session.pop(SESSION_PASSWORD_RESET_KEY, None)
            flash("Your password has been reset. Please log in with the new password.", "success")
            return redirect(url_for("auth.login"))

    return render_template(
        "pages/auth/reset.html",
        form=form,
        masked_email=mask_email(reset_state["email"]),
        otp_length=OTP_LENGTH,
        resend_cooldown_seconds=OTP_RESEND_COOLDOWN_SECONDS,
    )

@auth_bp.post("/reset/resend")
@limiter.limit("3 per minute")
def resend_reset_code():
    """Kirim ulang kode lupa password."""
    reset_state = get_password_reset_state()
    if reset_state is None:
        return expired_password_reset()
    try:
        resend_password_reset_code(reset_state)
    except AuthError as error:
        flash(str(error), "warning")
    else:
        session[SESSION_PASSWORD_RESET_KEY] = reset_state
        flash("If the email is registered, a new reset code has been sent", "success")
    return redirect(url_for("auth.reset_password"))

@auth_bp.post("/logout")
@login_required
def logout():
    """Logout. Sengaja POST biar ga bisa dipicu lewat link/gambar dari luar."""
    log_audit(AUDIT_ACTION_LOGOUT, "users", entity_id=current_user.id, user=current_user)
    db.session.execute(
        db.update(User).where(User.id == current_user.id)
        .values(session_version=User.session_version + 1)
    )
    db.session.commit()
    logout_user()
    session.clear()
    flash("You have logged out", "info")
    return redirect(url_for("auth.login"))
