from __future__ import annotations

from collections.abc import Mapping

from app.dto import (
    LoginData,
    PasswordChangeData,
    PasswordResetData,
    PasswordResetRequestData,
    RegistrationData,
)
from app.repositories import UserRepository

from .base_validator import BaseValidator


class RegistrationValidator(BaseValidator):
    def __init__(self, user_repository: UserRepository):
        self._user_repository = user_repository

    def build_data(self, form: Mapping[str, object]) -> RegistrationData:
        return RegistrationData(
            full_name=self._text(form, "full_name"),
            email=self._text(form, "email").lower(),
            location=self._text(form, "location"),
            password=str(form.get("password", "")),
            confirm_password=str(form.get("confirm_password", "")),
        )

    def validate(self, data: RegistrationData) -> dict[str, str]:
        errors: dict[str, str] = {}
        if not data.full_name:
            errors["full_name"] = "Full name is required."
        if "@" not in data.email or "." not in data.email.split("@")[-1]:
            errors["email"] = "Enter a valid email address."
        elif self._user_repository.find_by_email(data.email):
            errors["email"] = "An account with this email already exists."
        if not data.location:
            errors["location"] = "Location is required."
        if len(data.password) < 8:
            errors["password"] = "Password must be at least 8 characters."
        if data.password != data.confirm_password:
            errors["confirm_password"] = "Passwords must match."
        return errors


class LoginValidator(BaseValidator):
    def build_data(self, form: Mapping[str, object]) -> LoginData:
        return LoginData(
            email=self._text(form, "email").lower(),
            password=str(form.get("password", "")),
        )

    def validate(self, data: LoginData) -> dict[str, str]:
        errors: dict[str, str] = {}
        if not data.email:
            errors["email"] = "Email is required."
        if not data.password:
            errors["password"] = "Password is required."
        return errors


class PasswordResetRequestValidator(BaseValidator):
    def build_data(self, form: Mapping[str, object]) -> PasswordResetRequestData:
        return PasswordResetRequestData(email=self._text(form, "email").lower())

    def validate(self, data: PasswordResetRequestData) -> dict[str, str]:
        errors: dict[str, str] = {}
        if not data.email:
            errors["email"] = "Email is required."
        elif "@" not in data.email or "." not in data.email.split("@")[-1]:
            errors["email"] = "Enter a valid email address."
        return errors


class PasswordResetValidator(BaseValidator):
    def build_data(self, form: Mapping[str, object]) -> PasswordResetData:
        return PasswordResetData(
            password=str(form.get("password", "")),
            confirm_password=str(form.get("confirm_password", "")),
        )

    def validate(self, data: PasswordResetData) -> dict[str, str]:
        return _validate_new_password(data.password, data.confirm_password)


class PasswordChangeValidator(BaseValidator):
    def build_data(self, form: Mapping[str, object]) -> PasswordChangeData:
        return PasswordChangeData(
            current_password=str(form.get("current_password", "")),
            password=str(form.get("password", "")),
            confirm_password=str(form.get("confirm_password", "")),
        )

    def validate(self, data: PasswordChangeData) -> dict[str, str]:
        errors: dict[str, str] = {}
        if not data.current_password:
            errors["current_password"] = "Current password is required."
        errors.update(_validate_new_password(data.password, data.confirm_password))
        return errors


def _validate_new_password(password: str, confirm_password: str) -> dict[str, str]:
    errors: dict[str, str] = {}
    if len(password) < 8:
        errors["password"] = "Password must be at least 8 characters."
    if password != confirm_password:
        errors["confirm_password"] = "Passwords must match."
    return errors

