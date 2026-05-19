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
        follow_redirects=False,
    )
    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="alice@example.com").first()
        assert user is not None
        assert user.is_email_verified is False
        assert user.profile.location == "Kathmandu"
        assert user.credit_balance == 10
        assert user.verification_token is not None
        assert user.verification_token_expires is not None


def test_unverified_legacy_user_can_login_without_verification_step(app, client, login, user_factory):
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
        locked_user = User.query.filter_by(email="locked@example.com").first()
        assert locked_user.locked_until is not None


def test_verify_email_success(app, client):
    # Register user first
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
        user = User.query.filter_by(email="bob@example.com").first()
        assert user is not None
        assert user.is_email_verified is False
        token = user.verification_token

    # Verify email using the token
    response = client.get(f"/auth/verify-email/{token}", follow_redirects=True)
    assert response.status_code == 200
    assert b"Email verified successfully" in response.data

    with app.app_context():
        user = User.query.filter_by(email="bob@example.com").first()
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
        user = User.query.filter_by(email="charlie@example.com").first()
        assert user.is_email_verified is False
        old_expires = user.verification_token_expires

    # Resend verification
    response = client.post(
        "/auth/resend-verification",
        data={"email": "charlie@example.com"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"A new verification email has been sent" in response.data

    with app.app_context():
        user = User.query.filter_by(email="charlie@example.com").first()
        assert user.verification_token_expires > old_expires

