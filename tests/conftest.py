from __future__ import annotations

import pytest

from app import create_app
from app.database import Database
from app.models import Role, User
from config import TestConfig


@pytest.fixture()
def app():
    flask_app = create_app(TestConfig)
    with flask_app.app_context():
        _clear_database()
        Role.ensure("admin", "Administrator")
        Role.ensure("user", "Platform member")
    yield flask_app
    with flask_app.app_context():
        _clear_database()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def user_factory(app):
    def create_user(
        *,
        full_name: str = "Test Member",
        email: str = "member@example.com",
        password: str = "Password123!",
        location: str = "Kathmandu",
        role_name: str = "user",
        verified: bool = True,
    ) -> User:
        role = Role.ensure(
            role_name,
            "Administrator" if role_name == "admin" else "Platform member",
        )
        user = User.create_registered(full_name, email, password, location, role)
        if verified:
            user.mark_email_verified()
        return User.find_by_id(user.id)

    return create_user


@pytest.fixture()
def login(client):
    def do_login(email: str, password: str = "Password123!"):
        return client.post(
            "/auth/login",
            data={"email": email, "password": password},
            follow_redirects=True,
        )

    return do_login


def _clear_database() -> None:
    db = Database()
    try:
        db.execute("SET FOREIGN_KEY_CHECKS = 0")
        for table in (
            "admin_audit_logs",
            "profile_reviews",
            "profile_certificates",
            "profile_skills",
            "password_reset_tokens",
            "profiles",
            "users",
            "roles",
        ):
            db.execute(f"DELETE FROM {table}")
        db.execute("SET FOREIGN_KEY_CHECKS = 1")
    finally:
        db.close()
