from __future__ import annotations

import re
from datetime import datetime, timedelta

from app.database import Database
from app.models import User
from app.repositories import UserRepository
from app.utils.passwords import hash_reset_token


def test_registration_requires_email_verification(app, client):
    response = client.post(
        "/auth/register",
        data={
            "full_name": "Alice Example",
            "email": "alice@example.com",
            "location": "Kathmandu",
            "password": "Password123!",
            "confirm_password": "Password123!",
        },
    )
    assert response.status_code == 200
    with app.app_context():
        user = User.find_by_email("alice@example.com")
        assert user is not None
        assert user.is_email_verified is False
        assert user.profile.location == "Kathmandu"
        assert user.verification_token is not None
        assert user.verification_token_expires is not None


def test_unverified_user_can_login_for_current_scope(app, client, login, user_factory):
    with app.app_context():
        user_factory(email="legacy@example.com", verified=False)

    login_response = login("legacy@example.com")
    assert b"Dashboard" in login_response.data


def test_failed_logins_trigger_lockout(app, client, login, user_factory):
    with app.app_context():
        user_factory(email="locked@example.com")

    for _ in range(app.config["LOCKOUT_THRESHOLD"]):
        response = login("locked@example.com", "wrong-password")
        assert response.status_code == 200

    locked_response = login("locked@example.com", "Password123!")
    assert b"Too many failed attempts" in locked_response.data

    with app.app_context():
        locked_user = User.find_by_email("locked@example.com")
        assert locked_user.locked_until is not None


def test_verify_email_success(app, client):
    client.post(
        "/auth/register",
        data={
            "full_name": "Bob Tester",
            "email": "bob@example.com",
            "location": "Kathmandu",
            "password": "Password123!",
            "confirm_password": "Password123!",
        },
    )
    with app.app_context():
        user = User.find_by_email("bob@example.com")
        assert user is not None
        assert user.is_email_verified is False
        token = user.verification_token

    response = client.get(f"/auth/verify-email/{token}", follow_redirects=True)
    assert response.status_code == 200
    assert b"Email verified successfully" in response.data

    with app.app_context():
        user = User.find_by_email("bob@example.com")
        assert user.is_email_verified is True
        assert user.verification_token is None


def test_verify_email_invalid_token(app, client):
    response = client.get("/auth/verify-email/invalid_token", follow_redirects=True)
    assert response.status_code == 200
    assert b"The verification link is invalid or has expired" in response.data


def test_resend_verification_success(app, client):
    client.post(
        "/auth/register",
        data={
            "full_name": "Charlie Resend",
            "email": "charlie@example.com",
            "location": "Kathmandu",
            "password": "Password123!",
            "confirm_password": "Password123!",
        },
    )
    with app.app_context():
        user = User.find_by_email("charlie@example.com")
        assert user.is_email_verified is False
        old_expires = user.verification_token_expires

    response = client.post(
        "/auth/resend-verification",
        data={"email": "charlie@example.com"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Verify your email" in response.data

    with app.app_context():
        user = User.find_by_email("charlie@example.com")
        assert user.verification_token_expires >= old_expires


# ── US-02: Login / Logout Tests ──────────────────────────────────────────────


def test_login_success_redirects_to_dashboard(app, client, login, user_factory):
    """AC-1: Login accepts valid email and password; redirects to dashboard."""
    with app.app_context():
        user_factory(email="success@example.com")

    response = login("success@example.com", "Password123!")
    assert response.status_code == 200
    assert b"Dashboard" in response.data
    assert b"Welcome back" in response.data


def test_login_invalid_password_shows_inline_error(app, client, login, user_factory):
    """AC-1: Incorrect credentials display a clear error message."""
    with app.app_context():
        user_factory(email="wrong@example.com")

    response = login("wrong@example.com", "WrongPassword!")
    assert response.status_code == 200
    assert b"Invalid email or password" in response.data


def test_login_nonexistent_email_shows_error(app, client, login):
    """AC-1: Nonexistent email shows error message."""
    response = login("nobody@example.com", "Password123!")
    assert response.status_code == 200
    assert b"Invalid email or password" in response.data


def test_login_empty_fields_show_errors(app, client):
    """AC-1: Empty fields show inline validation errors."""
    response = client.post(
        "/auth/login",
        data={"email": "", "password": ""},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Email is required" in response.data
    assert b"Password is required" in response.data


def test_session_persists_across_pages(app, client, login, user_factory):
    """AC-2: Session is maintained across pages after login."""
    with app.app_context():
        user_factory(email="persist@example.com")

    login("persist@example.com", "Password123!")

    # Access protected page without re-logging in
    response = client.get("/dashboard", follow_redirects=True)
    assert response.status_code == 200
    assert b"Dashboard" in response.data


def test_logout_clears_session(app, client, login, user_factory):
    """AC-3: Logout immediately invalidates the session."""
    with app.app_context():
        user_factory(email="logout@example.com")

    login("logout@example.com", "Password123!")

    # Verify logged in
    response = client.get("/dashboard")
    assert response.status_code == 200

    # Logout via POST
    response = client.post("/auth/logout", follow_redirects=True)
    assert response.status_code == 200
    assert b"You have been logged out" in response.data

    # After logout, accessing dashboard should redirect to login
    response = client.get("/dashboard", follow_redirects=True)
    assert b"Log in" in response.data


def test_logout_via_get_also_works(app, client, login, user_factory):
    """AC-3: Logout via GET still works for backward compatibility."""
    with app.app_context():
        user_factory(email="getlogout@example.com")

    login("getlogout@example.com", "Password123!")
    response = client.get("/auth/logout", follow_redirects=True)
    assert response.status_code == 200
    assert b"You have been logged out" in response.data


def test_failed_count_increments_correctly(app, client, login, user_factory):
    """AC-4: Failed login count increments correctly to threshold."""
    with app.app_context():
        user_factory(email="counting@example.com")

    # First failed attempt
    login("counting@example.com", "wrong1")
    with app.app_context():
        user = User.find_by_email("counting@example.com")
        assert user.failed_login_count == 1

    # Second failed attempt
    login("counting@example.com", "wrong2")
    with app.app_context():
        user = User.find_by_email("counting@example.com")
        assert user.failed_login_count == 2

    # Third failed attempt triggers lockout
    login("counting@example.com", "wrong3")
    with app.app_context():
        user = User.find_by_email("counting@example.com")
        assert user.failed_login_count == 3
        assert user.locked_until is not None


def test_lockout_shows_minutes_remaining(app, client, login, user_factory):
    """AC-4: Lockout message shows time remaining."""
    with app.app_context():
        user_factory(email="timed@example.com")

    # Trigger lockout
    for _ in range(app.config["LOCKOUT_THRESHOLD"]):
        login("timed@example.com", "wrong-password")

    # Next attempt should show minutes remaining
    response = login("timed@example.com", "Password123!")
    assert response.status_code == 200
    assert b"Too many failed attempts" in response.data
    assert b"minute" in response.data


def test_successful_login_clears_failed_count(app, client, login, user_factory):
    """AC-4: Successful login resets the failed login counter."""
    with app.app_context():
        user_factory(email="reset@example.com")

    # One failed attempt
    login("reset@example.com", "wrong")
    with app.app_context():
        user = User.find_by_email("reset@example.com")
        assert user.failed_login_count == 1

    # Successful login should reset count
    login("reset@example.com", "Password123!")
    with app.app_context():
        user = User.find_by_email("reset@example.com")
        assert user.failed_login_count == 0
        assert user.locked_until is None


# US-03: Password Security Tests


def test_passwords_are_stored_as_secure_hashes(app, user_factory):
    """AC-1/2: Passwords are stored as secure hashes, never plain text."""
    with app.app_context():
        user = user_factory(email="hashed@example.com", password="Password123!")

        assert user.password_hash != "Password123!"
        assert "Password123!" not in user.password_hash
        assert user.password_hash.startswith(app.config["PASSWORD_HASH_METHOD"])
        assert user.check_password("Password123!") is True


def test_forgot_password_creates_one_time_token_with_30_minute_expiry(app, client, user_factory):
    """AC-3: Password reset emails use one-time tokens expiring within 30 minutes."""
    with app.app_context():
        user_factory(email="recover@example.com")
        app.config["MAIL_LOG_FILE"].unlink(missing_ok=True)

    response = client.post(
        "/auth/forgot-password",
        data={"email": "recover@example.com"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"30-minute password reset link" in response.data

    with app.app_context():
        log_text = app.config["MAIL_LOG_FILE"].read_text(encoding="utf-8")
        token = _extract_reset_token(log_text)
        db = Database()
        try:
            row = db.fetch_one(
                """
                SELECT token_hash, expires_at, used_at
                FROM password_reset_tokens
                WHERE token_hash = %s
                """,
                (hash_reset_token(token),),
            )
        finally:
            db.close()

        assert row is not None
        assert row["used_at"] is None
        assert token not in row["token_hash"]
        assert (
            datetime.utcnow() + timedelta(minutes=29)
            <= row["expires_at"]
            <= datetime.utcnow() + timedelta(minutes=31)
        )
        assert "Password123!" not in log_text


def test_reset_password_updates_password_and_consumes_token(app, client, login, user_factory):
    """AC-3: Reset tokens work once and update the stored password hash."""
    with app.app_context():
        user_factory(email="reset-link@example.com")
        app.config["MAIL_LOG_FILE"].unlink(missing_ok=True)

    client.post("/auth/forgot-password", data={"email": "reset-link@example.com"})

    with app.app_context():
        token = _extract_reset_token(app.config["MAIL_LOG_FILE"].read_text(encoding="utf-8"))
        old_hash = User.find_by_email("reset-link@example.com").password_hash

    response = client.post(
        f"/auth/reset-password/{token}",
        data={"password": "NewPassword123!", "confirm_password": "NewPassword123!"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Your password has been reset" in response.data

    with app.app_context():
        user = User.find_by_email("reset-link@example.com")
        assert user.password_hash != old_hash
        assert user.check_password("NewPassword123!") is True

    old_login = login("reset-link@example.com", "Password123!")
    assert b"Invalid email or password" in old_login.data

    new_login = login("reset-link@example.com", "NewPassword123!")
    assert b"Dashboard" in new_login.data

    reused_response = client.post(
        f"/auth/reset-password/{token}",
        data={"password": "Another123!", "confirm_password": "Another123!"},
    )
    assert b"invalid, expired, or has already been used" in reused_response.data


def test_expired_password_reset_token_is_rejected(app, client, login, user_factory):
    """AC-3: Expired reset tokens cannot change credentials."""
    raw_token = "expired-reset-token"
    with app.app_context():
        user = user_factory(email="expired@example.com")
        UserRepository().create_password_reset_token(
            user,
            hash_reset_token(raw_token),
            datetime.utcnow() - timedelta(minutes=1),
        )

    response = client.post(
        f"/auth/reset-password/{raw_token}",
        data={"password": "NewPassword123!", "confirm_password": "NewPassword123!"},
    )

    assert response.status_code == 200
    assert b"invalid, expired, or has already been used" in response.data

    old_login = login("expired@example.com", "Password123!")
    assert b"Dashboard" in old_login.data


def test_profile_change_password_requires_current_password(app, client, login, user_factory):
    """AC-4: Profile password changes require the current password first."""
    with app.app_context():
        user_factory(email="current-required@example.com")

    login("current-required@example.com")
    response = client.post(
        "/auth/change-password",
        data={
            "current_password": "WrongPassword!",
            "password": "NewPassword123!",
            "confirm_password": "NewPassword123!",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Current password is incorrect" in response.data


def test_profile_change_password_updates_login_password(app, client, login, user_factory):
    """AC-4: Users can change passwords from profile settings."""
    with app.app_context():
        user_factory(email="change-password@example.com")

    login("change-password@example.com")
    response = client.post(
        "/auth/change-password",
        data={
            "current_password": "Password123!",
            "password": "ChangedPassword123!",
            "confirm_password": "ChangedPassword123!",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Your password has been changed securely" in response.data

    client.post("/auth/logout", follow_redirects=True)
    old_login = login("change-password@example.com", "Password123!")
    assert b"Invalid email or password" in old_login.data

    new_login = login("change-password@example.com", "ChangedPassword123!")
    assert b"Dashboard" in new_login.data


def _extract_reset_token(log_text: str) -> str:
    match = re.search(r"/auth/reset-password/([A-Za-z0-9_-]+)", log_text)
    assert match, log_text
    return match.group(1)
