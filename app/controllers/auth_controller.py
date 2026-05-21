from __future__ import annotations

from flask import current_app, flash, redirect, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.dto import LoginData
from app.exceptions import (
    AccountLockedError,
    DuplicateEmailError,
    InactiveAccountError,
    InvalidCurrentPasswordError,
    InvalidCredentialsError,
    InvalidPasswordResetTokenError,
    InvalidVerificationTokenError,
    UserNotFoundError,
)
from app.services import AuthService
from app.utils.email import send_email
from app.validators import (
    LoginValidator,
    PasswordChangeValidator,
    PasswordResetRequestValidator,
    PasswordResetValidator,
    RegistrationValidator,
)

from .base_controller import BaseController


class AuthController(BaseController):
    def __init__(
        self,
        auth_service: AuthService,
        registration_validator: RegistrationValidator,
        login_validator: LoginValidator,
        password_reset_request_validator: PasswordResetRequestValidator,
        password_reset_validator: PasswordResetValidator,
        password_change_validator: PasswordChangeValidator,
    ):
        self._auth_service = auth_service
        self._registration_validator = registration_validator
        self._login_validator = login_validator
        self._password_reset_request_validator = password_reset_request_validator
        self._password_reset_validator = password_reset_validator
        self._password_change_validator = password_change_validator

    def register(self):
        if current_user.is_authenticated:
            return redirect(url_for("main.dashboard"))

        registration_data = self._registration_validator.build_data(request.form)
        errors: dict[str, str] = {}
        values = registration_data.values

        if request.method == "POST":
            errors = self._registration_validator.validate(registration_data)
            if not errors:
                try:
                    user = self._auth_service.register_user(registration_data)
                except DuplicateEmailError:
                    errors["email"] = "An account with this email already exists."
                else:
                    verification_url = url_for(
                        "auth.verify_email",
                        token=user.verification_token,
                        _external=True,
                    )
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
                    return self.render("auth/verify_email_pending.html", email=user.email)

        return self.render("auth/register.html", errors=errors, values=values)

    def verify_email(self, token: str):
        try:
            _user, already_verified = self._auth_service.verify_email(token)
        except InvalidVerificationTokenError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("auth.register"))
        except UserNotFoundError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("auth.register"))

        if already_verified:
            flash("Your email is already verified.", "info")
        else:
            flash("Email verified successfully! Welcome to Sahayogi.", "success")
        return redirect(url_for("auth.login"))

    def login(self):
        if current_user.is_authenticated:
            return redirect(url_for("main.dashboard"))

        errors: dict[str, str] = {}
        login_data = LoginData(email="", password="")

        if request.method == "POST":
            login_data = self._login_validator.build_data(request.form)
            errors = self._login_validator.validate(login_data)

            if not errors:
                try:
                    user = self._auth_service.authenticate(
                        login_data,
                        lockout_threshold=current_app.config["LOCKOUT_THRESHOLD"],
                        lockout_duration_minutes=current_app.config["LOCKOUT_DURATION_MINUTES"],
                    )
                except AccountLockedError as exc:
                    if exc.fresh_lock:
                        errors["locked"] = (
                            f"Too many failed attempts. Account locked for "
                            f"{current_app.config['LOCKOUT_DURATION_MINUTES']} minutes."
                        )
                    else:
                        errors["locked"] = str(exc)
                except InvalidCredentialsError as exc:
                    errors[exc.field] = str(exc)
                except InactiveAccountError as exc:
                    errors["email"] = str(exc)
                else:
                    login_user(user, remember=True)
                    session.permanent = True
                    flash("Welcome back.", "success")
                    return redirect(request.args.get("next") or url_for("main.dashboard"))

        return self.render("auth/login.html", email=login_data.email, errors=errors)

    @login_required
    def logout(self):
        logout_user()
        # Remove app-specific session data; logout_user() already
        # handles _user_id and the remember-me cookie signal.
        session.pop("csrf_token", None)
        flash("You have been logged out.", "info")
        return redirect(url_for("main.home"))

    def profile_setup(self):
        flash("Please log in to continue.", "info")
        return redirect(url_for("auth.login"))

    def resend_verification(self):
        if request.method == "POST":
            email = request.form.get("email", "").lower().strip()
            user = self._auth_service.resend_verification(email)
            if user:
                send_email(
                    "Verify your Sahayogi email",
                    user.email,
                    url_for("auth.verify_email", token=user.verification_token, _external=True),
                )
                return self.render("auth/verify_email_pending.html", email=user.email)
            flash("If that email exists and is unverified, a new link has been sent.", "info")
        return self.render("auth/resend_verification.html")

    def forgot_password(self):
        errors: dict[str, str] = {}
        reset_request = self._password_reset_request_validator.build_data(request.form)

        if request.method == "POST":
            errors = self._password_reset_request_validator.validate(reset_request)
            if not errors:
                user, token = self._auth_service.request_password_reset(
                    reset_request.email,
                    expiry_seconds=current_app.config["PASSWORD_RESET_EXPIRY_SECONDS"],
                )
                if user and token:
                    reset_url = url_for("auth.reset_password", token=token, _external=True)
                    send_email(
                        "Reset your Sahayogi password",
                        user.email,
                        (
                            f"Hello {user.full_name},\n\n"
                            f"Reset your Sahayogi password using this one-time link:\n"
                            f"{reset_url}\n\n"
                            "This link expires in 30 minutes. If you did not request it, you can ignore this email."
                        ),
                    )
                flash(
                    "If that email belongs to an account, a 30-minute password reset link has been sent.",
                    "info",
                )
                if not current_app.config.get("MAIL_SERVER"):
                    flash(
                        f"Development email links are written to {current_app.config['MAIL_LOG_FILE']}.",
                        "warning",
                    )
                return redirect(url_for("auth.login"))
        return self.render("auth/forgot_password.html", email=reset_request.email, errors=errors)

    def reset_password(self, token: str):
        errors: dict[str, str] = {}
        token_is_valid = self._auth_service.password_reset_token_is_valid(token)
        reset_data = self._password_reset_validator.build_data(request.form)

        if request.method == "POST":
            errors = self._password_reset_validator.validate(reset_data)
            if not errors:
                try:
                    self._auth_service.reset_password(token, reset_data.password)
                except InvalidPasswordResetTokenError as exc:
                    errors["token"] = str(exc)
                else:
                    flash("Your password has been reset. Please log in with the new password.", "success")
                    return redirect(url_for("auth.login"))

        return self.render(
            "auth/reset_password.html",
            errors=errors,
            token_is_valid=token_is_valid,
        )

    @login_required
    def change_password(self):
        password_data = self._password_change_validator.build_data(request.form)
        errors = self._password_change_validator.validate(password_data)

        if not errors:
            try:
                self._auth_service.change_password(
                    current_user.id,
                    password_data.current_password,
                    password_data.password,
                )
            except InvalidCurrentPasswordError as exc:
                errors["current_password"] = str(exc)
            except UserNotFoundError as exc:
                errors["current_password"] = str(exc)
            else:
                flash("Your password has been changed securely.", "success")
                return redirect(url_for("profile.edit"))

        for message in errors.values():
            flash(message, "danger")
        return redirect(url_for("profile.edit"))
