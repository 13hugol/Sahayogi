from __future__ import annotations

from datetime import datetime, timedelta

from app.dto import LoginData, RegistrationData
from app.enums import AccountStatus, UserRole
from app.exceptions import (
    AccountLockedError,
    DuplicateEmailError,
    InactiveAccountError,
    InvalidCredentialsError,
    InvalidVerificationTokenError,
    UserNotFoundError,
)
from app.repositories import RoleRepository, UserRepository
from app.utils.tokens import generate_token, validate_token


class AuthService:
    def __init__(
        self,
        user_repository: UserRepository,
        role_repository: RoleRepository,
        *,
        token_generator=generate_token,
        token_validator=validate_token,
    ):
        self._user_repository = user_repository
        self._role_repository = role_repository
        self._token_generator = token_generator
        self._token_validator = token_validator

    def register_user(self, data: RegistrationData):
        if self._user_repository.find_by_email(data.email):
            raise DuplicateEmailError(data.email)
        role = self._role_repository.ensure(UserRole.USER)
        user = self._user_repository.create_registered(
            data.full_name,
            data.email,
            data.password,
            data.location,
            role,
        )
        self.refresh_verification_token(user)
        return user

    def refresh_verification_token(self, user):
        token = self._token_generator(user.email, "email-verification")
        self._user_repository.save_verification_token(user, token, datetime.utcnow() + timedelta(hours=24))
        return token

    def verify_email(self, token: str):
        email = self._token_validator(token, "email-verification", 86400)
        if not email:
            raise InvalidVerificationTokenError()
        user = self._user_repository.find_by_email(email)
        if not user:
            raise UserNotFoundError("Account not found.")
        already_verified = user.is_email_verified
        if not already_verified:
            self._user_repository.mark_email_verified(user)
        return user, already_verified

    def resend_verification(self, email: str):
        user = self._user_repository.find_by_email(email)
        if not user or user.is_email_verified:
            return None
        self.refresh_verification_token(user)
        return user

    def authenticate(self, data: LoginData, *, lockout_threshold: int, lockout_duration_minutes: int):
        user = self._user_repository.find_by_email(data.email)
        if not user:
            raise InvalidCredentialsError(field="email")

        if user.is_locked:
            raise AccountLockedError(minutes_remaining=user.minutes_until_unlock(), locked_until=user.locked_until)

        if user.has_lockout_expired:
            self._user_repository.clear_failed_login(user)

        if not user.check_password(data.password):
            locked_until = None
            if user.failed_login_count + 1 >= lockout_threshold:
                locked_until = datetime.utcnow() + timedelta(minutes=lockout_duration_minutes)
            self._user_repository.register_failed_login(user, locked_until)
            if locked_until:
                raise AccountLockedError(
                    minutes_remaining=lockout_duration_minutes,
                    locked_until=locked_until,
                    fresh_lock=True,
                )
            raise InvalidCredentialsError(field="password")

        if user.status != AccountStatus.ACTIVE.value:
            raise InactiveAccountError()

        self._user_repository.clear_failed_login(user)
        return user
