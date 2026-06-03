from __future__ import annotations

from datetime import datetime


class SahayogiException(Exception):
    """Base exception for application-level errors."""


class ValidationError(SahayogiException):
    def __init__(self, errors: dict[str, str]):
        super().__init__("Validation failed.")
        self.errors = errors


class UserNotFoundError(SahayogiException):
    def __init__(self, message: str = "User not found."):
        super().__init__(message)


class ProfileNotFoundError(SahayogiException):
    def __init__(self, user_id: int):
        super().__init__(f"Profile for user {user_id} was not found.")
        self.user_id = user_id


class CategoryNotFoundError(SahayogiException):
    def __init__(self, category_id: int):
        super().__init__(f"Category {category_id} was not found.")
        self.category_id = category_id


class DuplicateEmailError(SahayogiException):
    def __init__(self, email: str):
        super().__init__(f"An account with email '{email}' already exists.")
        self.email = email


class InvalidCredentialsError(SahayogiException):
    def __init__(self, message: str = "Invalid email or password.", *, field: str = "email"):
        super().__init__(message)
        self.field = field


class InactiveAccountError(SahayogiException):
    def __init__(self, message: str = "This account is not active."):
        super().__init__(message)


class AccountLockedError(SahayogiException):
    def __init__(
        self,
        *,
        minutes_remaining: int,
        locked_until: datetime | None = None,
        fresh_lock: bool = False,
    ):
        message = f"Too many failed attempts. Try again in {minutes_remaining} minute{'s' if minutes_remaining != 1 else ''}."
        super().__init__(message)
        self.minutes_remaining = minutes_remaining
        self.locked_until = locked_until
        self.fresh_lock = fresh_lock


class InvalidVerificationTokenError(SahayogiException):
    def __init__(self):
        super().__init__("The verification link is invalid or has expired.")


class InvalidPasswordResetTokenError(SahayogiException):
    def __init__(self):
        super().__init__("The password reset link is invalid, expired, or has already been used.")


class InvalidCurrentPasswordError(SahayogiException):
    def __init__(self):
        super().__init__("Current password is incorrect.")


class InvalidRoleError(SahayogiException):
    def __init__(self, role_name: str):
        super().__init__(f"Invalid role '{role_name}'.")
        self.role_name = role_name


class SelfRoleChangeError(SahayogiException):
    def __init__(self):
        super().__init__("You cannot change your own role.")


class InvalidSkillTypeError(SahayogiException):
    def __init__(self, skill_type: str):
        super().__init__(f"Invalid skill type '{skill_type}'.")
        self.skill_type = skill_type
