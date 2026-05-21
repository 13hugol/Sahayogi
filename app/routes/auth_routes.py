from __future__ import annotations

from flask import Blueprint

from ..controllers.auth_controller import AuthController


class AuthRoutes:
    def __init__(self):
        self.bp = Blueprint("auth", __name__, url_prefix="/auth")
        self.controller = AuthController()

    def register(self):
        self.bp.route("/register", methods=["GET", "POST"])(self.controller.register)
        self.bp.route("/verify-email/<token>", methods=["GET"])(self.controller.verify_email)
        self.bp.route("/profile-setup", methods=["GET", "POST"])(self.controller.profile_setup)
        self.bp.route("/resend-verification", methods=["GET", "POST"])(self.controller.resend_verification)
        self.bp.route("/login", methods=["GET", "POST"])(self.controller.login)
        self.bp.route("/logout", methods=["GET", "POST"])(self.controller.logout)
        self.bp.route("/forgot-password", methods=["GET", "POST"])(self.controller.forgot_password)
        return self.bp

