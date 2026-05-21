from __future__ import annotations

from app.models import User


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
