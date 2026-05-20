from __future__ import annotations

from datetime import datetime, timedelta

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.models import Role, User
from app.utils.email import send_email
from app.utils.tokens import generate_token, validate_token
from .base_controller import BaseController


class AuthController(BaseController):
    def register(self):
        if current_user.is_authenticated:
            return redirect(url_for("main.dashboard"))

        errors: dict[str, str] = {}
        values = {
            "full_name": request.form.get("full_name", "").strip(),
            "email": request.form.get("email", "").lower().strip(),
            "location": request.form.get("location", "").strip(),
        }
        if request.method == "POST":
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")
            if not values["full_name"]:
                errors["full_name"] = "Full name is required."
            if "@" not in values["email"] or "." not in values["email"].split("@")[-1]:
                errors["email"] = "Enter a valid email address."
            elif User.find_by_email(values["email"]):
                errors["email"] = "An account with this email already exists."
            if not values["location"]:
                errors["location"] = "Location is required."
            if len(password) < 8:
                errors["password"] = "Password must be at least 8 characters."
            if password != confirm_password:
                errors["confirm_password"] = "Passwords must match."

            if not errors:
                role = Role.ensure("user", "Platform member")
                user = User.create_registered(
                    values["full_name"],
                    values["email"],
                    password,
                    values["location"],
                    role,
                )
                token = generate_token(user.email, "email-verification")
                user.save_verification_token(token, datetime.utcnow() + timedelta(hours=24))
                verification_url = url_for("auth.verify_email", token=token, _external=True)
                email_sent = send_email(
                    "Verify your Sahayogi email",
                    user.email,
                    (
                        f"Welcome {user.full_name}! Please verify your email by visiting:\n"
                        f"{verification_url}\n\nThis link expires in 24 hours."
                    ),
                )
                if email_sent:
                    flash("Account created. A verification email has been sent.", "info")
                else:
                    flash(
                        f"Account created. Email delivery is not configured, so the verification link was saved in {current_app.config['MAIL_LOG_FILE']}.",
                        "warning",
                    )
                return render_template("auth/verify_email_pending.html", email=user.email)

        return render_template("auth/register.html", errors=errors, values=values)

    def verify_email(self, token: str):
        email = validate_token(token, "email-verification", 86400)
        if not email:
            flash("The verification link is invalid or has expired.", "danger")
            return redirect(url_for("auth.register"))
        user = User.find_by_email(email)
        if not user:
            flash("Account not found.", "danger")
            return redirect(url_for("auth.register"))
        if user.is_email_verified:
            flash("Your email is already verified.", "info")
        else:
            user.mark_email_verified()
            flash("Email verified successfully! Welcome to Sahayogi.", "success")
        return redirect(url_for("auth.login"))

    def login(self):
        if current_user.is_authenticated:
            return redirect(url_for("main.dashboard"))

        if request.method == "POST":
            email = request.form.get("email", "").lower().strip()
            password = request.form.get("password", "")
            user = User.find_by_email(email)
            if not user:
                flash("Invalid email or password.", "danger")
                return render_template("auth/login.html", email=email)
            if user.locked_until and user.locked_until > datetime.utcnow():
                flash("Too many failed attempts. Try again after the lockout period.", "danger")
                return render_template("auth/login.html", email=email)
            if not user.check_password(password):
                locked_until = None
                if user.failed_login_count + 1 >= current_app.config["LOCKOUT_THRESHOLD"]:
                    locked_until = datetime.utcnow() + timedelta(
                        minutes=current_app.config["LOCKOUT_DURATION_MINUTES"]
                    )
                user.register_failed_login(locked_until)
                flash("Invalid email or password.", "danger")
                return render_template("auth/login.html", email=email)
            if user.status != "active":
                flash("This account is not active.", "danger")
                return render_template("auth/login.html", email=email)
            user.clear_failed_login()
            login_user(user)
            flash("Welcome back.", "success")
            return redirect(request.args.get("next") or url_for("main.dashboard"))
        return render_template("auth/login.html")

    @login_required
    def logout(self):
        logout_user()
        flash("You have been logged out.", "info")
        return redirect(url_for("main.home"))

    def profile_setup(self):
        flash("Please log in to continue.", "info")
        return redirect(url_for("auth.login"))

    def resend_verification(self):
        if request.method == "POST":
            email = request.form.get("email", "").lower().strip()
            user = User.find_by_email(email)
            if user and not user.is_email_verified:
                token = generate_token(user.email, "email-verification")
                user.save_verification_token(token, datetime.utcnow() + timedelta(hours=24))
                verification_url = url_for("auth.verify_email", token=token, _external=True)
                send_email("Verify your Sahayogi email", user.email, verification_url)
                return render_template("auth/verify_email_pending.html", email=user.email)
            flash("If that email exists and is unverified, a new link has been sent.", "info")
        return render_template("auth/resend_verification.html")

    def forgot_password(self):
        if request.method == "POST":
            flash("Password reset is outside the current backend scope.", "info")
            return redirect(url_for("auth.login"))
        return render_template("auth/forgot_password.html")
