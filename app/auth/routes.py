from __future__ import annotations

from datetime import datetime, timedelta

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..forms import LoginForm, RegistrationForm, RequestResetForm, ResetPasswordForm
from ..models import Profile, Role, User, utcnow
from ..services import (
    build_absolute_url,
    clear_failed_logins,
    generate_token,
    normalize_account_status,
    register_failed_login,
    seed_initial_credits,
    send_email,
    unique_username,
    validate_token,
)
from . import auth_bp


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = RegistrationForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data.lower()).first():
            form.email.errors.append("An account with this email already exists.")
        else:
            role = Role.query.filter_by(name="user").first()
            if not role:
                role = Role(name="user", description="Platform member")
                db.session.add(role)
                db.session.flush()
            user = User(
                full_name=form.full_name.data.strip(),
                email=form.email.data.lower().strip(),
                role=role,
            )
            user.set_password(form.password.data)
            user.profile = Profile(
                username=unique_username(form.email.data.split("@")[0]),
                contact_email=form.email.data.lower().strip(),
                location=form.location.data.strip(),
            )
            db.session.add(user)
            db.session.flush()
            seed_initial_credits(user)
            verification_token = generate_token(user.email, "email-verification")
            user.verification_token = verification_token
            user.verification_token_expires = utcnow() + timedelta(hours=24)
            db.session.commit()
            verification_url = build_absolute_url("auth.verify_email", token=verification_token)
            send_email(
                "Verify your Sahayogi email",
                user.email,
                (
                    f"Welcome {user.full_name}! Please verify your email by visiting:\n"
                    f"{verification_url}\n\n"
                    "This link expires in 24 hours."
                ),
            )
            flash(
                "Account created. A verification email has been sent. Please check your inbox.",
                "info",
            )
            return render_template("auth/verify_email_pending.html", email=user.email)
    return render_template("auth/register.html", form=form)


@auth_bp.route("/verify-email/<token>", methods=["GET"])
def verify_email(token: str):
    email = validate_token(token, "email-verification", 86400)
    if not email:
        flash("The verification link is invalid or has expired.", "danger")
        return redirect(url_for("auth.register"))
    user = User.query.filter_by(email=email).first_or_404()
    if user.is_email_verified:
        flash("Your email is already verified.", "info")
    else:
        user.is_email_verified = True
        user.verification_token = None
        user.verification_token_expires = None
        db.session.commit()
        flash("Email verified successfully! Welcome to Sahayogi.", "success")
    return redirect(url_for("auth.profile_setup"))


@auth_bp.route("/profile-setup", methods=["GET", "POST"])
def profile_setup():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    flash("Please log in to complete your profile setup.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/resend-verification", methods=["GET", "POST"])
def resend_verification():
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        user = User.query.filter_by(email=email).first()
        if user and not user.is_email_verified:
            verification_token = generate_token(user.email, "email-verification")
            user.verification_token = verification_token
            user.verification_token_expires = utcnow() + timedelta(hours=24)
            db.session.commit()
            verification_url = build_absolute_url("auth.verify_email", token=verification_token)
            send_email(
                "Verify your Sahayogi email",
                user.email,
                (
                    f"Welcome {user.full_name}! Please verify your email by visiting:\n"
                    f"{verification_url}\n\n"
                    "This link expires in 24 hours."
                ),
            )
            flash("A new verification email has been sent.", "info")
            return render_template("auth/verify_email_pending.html", email=user.email)
        flash("If that email exists and is unverified, a new link has been sent.", "info")
    return render_template("auth/resend_verification.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if not user:
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html", form=form)
        normalize_account_status(user)
        if user.locked_until and user.locked_until > utcnow():
            flash("Too many failed attempts. Try again after the lockout period.", "danger")
            return render_template("auth/login.html", form=form)
        if not user.check_password(form.password.data):
            register_failed_login(user)
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html", form=form)
        if user.deleted_at or user.status == "deleted":
            flash("This account is scheduled for deletion and cannot be accessed.", "danger")
            return render_template("auth/login.html", form=form)
        if user.status == "banned":
            flash("This account has been banned.", "danger")
            return render_template("auth/login.html", form=form)
        if user.status == "suspended" and not user.is_active:
            flash("This account is suspended.", "warning")
            return render_template("auth/login.html", form=form)
        clear_failed_logins(user)
        login_user(user)
        flash("Welcome back.", "success")
        next_url = request.args.get("next")
        return redirect(next_url or url_for("main.dashboard"))
    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.home"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user:
            token = generate_token(user.email, "password-reset")
            reset_url = build_absolute_url("auth.reset_password", token=token)
            send_email(
                "Reset your Sahayogi password",
                user.email,
                (
                    f"Reset your password by visiting:\n{reset_url}\n\n"
                    "This link expires in 30 minutes."
                ),
            )
        flash("If that email exists, a reset link has been sent.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    email = validate_token(
        token,
        "password-reset",
        current_app.config["PASSWORD_RESET_EXPIRY_SECONDS"],
    )
    if not email:
        flash("That reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.forgot_password"))
    user = User.query.filter_by(email=email).first_or_404()
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Password updated. You can now log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form)
