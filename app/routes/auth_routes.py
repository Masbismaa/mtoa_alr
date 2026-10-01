"""Route register, login 2 langkah (password -> OTP), kirim ulang OTP, dan logout."""
from flask import Blueprint, flash, redirect, render_template, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db, limiter
from app.models import User
from app.schemas.auth_schema import LoginForm, OtpForm, RegisterForm
from app.services.audit_service import log_audit
from app.services.auth_service import (
    authenticate_user,
    can_continue_login,
    register_user,
    resend_otp_challenge,
    start_otp_challenge,
    verify_otp_code,
    authenticate_user,
)
from app.utils.constants import (
    AUDIT_ACTION_LOGOUT,
    OTP_LENGTH,
    OTP_RESEND_COOLDOWN_SECONDS,
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
            register_user(
                email=form.email.data,
                password=form.password.data,
                full_name=form.full_name.data,
                department=form.department.data,
                job_title=form.job_title.data,
            )
        except AuthError as error:
            flash(str(error), "danger")
        else:
            flash("Akun berhasil dibuat, silakan login", "success")
            return redirect(url_for("auth.login"))

    return render_template("pages/auth/register.html", form=form)

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
        except AuthError as error:
            flash(str(error), "danger")
        else:
            start_otp_challenge(user)
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
        flash("Sesi login habis, silakan login ulang", "warning")
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
        flash("Sesi login habis, silakan login ulang", "warning")
        return redirect(url_for("auth.login"))

    try:
        resend_otp_challenge(pending_user)
    except AuthError as error:
        if not can_continue_login(pending_user):
            return end_pending_login(str(error))
        flash(str(error), "warning")
    else:
        flash("OTP baru sudah dikirim", "success")
    return redirect(url_for("auth.verify_otp"))

@auth_bp.post("/logout")
@login_required
def logout():
    """Logout. Sengaja POST biar ga bisa dipicu lewat link/gambar dari luar."""
    log_audit(AUDIT_ACTION_LOGOUT, "users", entity_id=current_user.id, user=current_user, is_commit=True)
    logout_user()
    session.clear()
    flash("Kamu sudah logout", "info")
    return redirect(url_for("auth.login"))