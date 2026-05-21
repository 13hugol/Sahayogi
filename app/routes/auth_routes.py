from __future__ import annotations

from flask import Blueprint

from ..controllers.auth_controller import AuthController
from ..repositories import ProfileRepository, RoleRepository, UserRepository
from ..services import AuthService
from ..validators import LoginValidator, RegistrationValidator


class AuthRoutes:
    def __init__(self):
        self.bp = Blueprint("auth", __name__, url_prefix="/auth")
        role_repository = RoleRepository()
        profile_repository = ProfileRepository()
        user_repository = UserRepository(
            role_repository=role_repository,
            profile_repository=profile_repository,
        )
        self.controller = AuthController(
            AuthService(user_repository, role_repository),
            RegistrationValidator(user_repository),
            LoginValidator(),
        )

    def register(self):
        self.bp.route("/register", methods=["GET", "POST"])(self.controller.register)
        self.bp.route("/verify-email/<token>", methods=["GET"])(self.controller.verify_email)
        self.bp.route("/profile-setup", methods=["GET", "POST"])(self.controller.profile_setup)
        self.bp.route("/resend-verification", methods=["GET", "POST"])(self.controller.resend_verification)
        self.bp.route("/login", methods=["GET", "POST"])(self.controller.login)
        self.bp.route("/logout", methods=["GET", "POST"])(self.controller.logout)
        self.bp.route("/forgot-password", methods=["GET", "POST"])(self.controller.forgot_password)
        return self.bp
