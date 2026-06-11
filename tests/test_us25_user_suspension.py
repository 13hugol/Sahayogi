from __future__ import annotations

from datetime import datetime, timedelta
import pytest
from app.database import Database
from app.exceptions import InactiveAccountError
from app.models.skill import Skill, Category
from app.models.profile import ProfileSkill
from app.repositories import UserRepository, SkillRepository, CategoryRepository
from app.enums import SkillType


@pytest.fixture()
def setup_users(app, user_factory):
    with app.app_context():
        # Create categories and users
        cat_repo = CategoryRepository()
        tech = cat_repo.ensure("Tech", "Tech skills")

        admin = user_factory(email="admin@example.com", full_name="Charlie Admin", role_name="admin")
        alice = user_factory(email="alice@example.com", full_name="Alice User")
        bob = user_factory(email="bob@example.com", full_name="Bob User")

        # Give Alice an active listing
        ps_alice = ProfileSkill.create(alice.id, "Python coding", SkillType.OFFERED)
        db = Database()
        db.execute(
            """
            INSERT INTO skills (user_id, category_id, skill_id, title, description, exchange_type, credit_cost, availability, location_text, contact_method, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'approved')
            """,
            (alice.id, tech.id, ps_alice.id, "Alice Python Basics", "Learn Python", "credit", 10, "Daily", "Kathmandu", "Platform")
        )
        db.close()

        return {"admin": admin, "alice": alice, "bob": bob}


def test_suspend_ban_access_control(client, login, setup_users):
    # 1. Anonymous user cannot suspend
    res = client.post(f"/admin/users/{setup_users['alice'].id}/suspend", data={"days": 7, "reason": "Spam"})
    assert res.status_code == 302
    assert "/auth/login" in res.headers["Location"]

    # 2. Regular user cannot suspend
    login("bob@example.com")
    res = client.post(f"/admin/users/{setup_users['alice'].id}/suspend", data={"days": 7, "reason": "Spam"})
    assert res.status_code == 403

    # Logout
    client.get("/auth/logout")

    # 3. Anonymous user cannot ban
    res = client.post(f"/admin/users/{setup_users['alice'].id}/ban", data={"reason": "Abuse"})
    assert res.status_code == 302

    # 4. Regular user cannot ban
    login("bob@example.com")
    res = client.post(f"/admin/users/{setup_users['alice'].id}/ban", data={"reason": "Abuse"})
    assert res.status_code == 403


def test_admin_cannot_enforce_self(client, login, setup_users):
    login("admin@example.com")
    # Try to suspend self
    res = client.post(f"/admin/users/{setup_users['admin'].id}/suspend", data={"days": 7, "reason": "Self"}, follow_redirects=True)
    assert res.status_code == 200
    assert b"cannot suspend yourself" in res.data

    # Try to ban self
    res = client.post(f"/admin/users/{setup_users['admin'].id}/ban", data={"reason": "Self"}, follow_redirects=True)
    assert res.status_code == 200
    assert b"cannot ban yourself" in res.data


def test_user_suspension_flow(app, client, login, setup_users):
    # 1. Admin suspends Alice
    login("admin@example.com")
    res = client.post(
        f"/admin/users/{setup_users['alice'].id}/suspend",
        data={"days": 5, "reason": "Inappropriate content"},
        follow_redirects=True
    )
    assert res.status_code == 200
    assert b"temporarily suspended" in res.data

    # Verify DB status
    with app.app_context():
        user = UserRepository().find_by_id(setup_users["alice"].id)
        assert user.status == "suspended"
        assert user.suspension_reason == "Inappropriate content"
        assert user.suspended_until is not None

        # Verify audit log
        db = Database()
        audit = db.fetch_one("SELECT * FROM admin_audit_logs WHERE action = 'suspend_user' ORDER BY created_at DESC")
        assert audit is not None
        assert audit["admin_id"] == setup_users["admin"].id
        assert audit["target_id"] == setup_users["alice"].id
        assert "Suspended for 5 days" in audit["detail"]
        db.close()

    # 2. Try to log in as suspended user
    client.get("/auth/logout")
    res = client.post(
        "/auth/login",
        data={"email": "alice@example.com", "password": "Password123!"},
        follow_redirects=True
    )
    assert res.status_code == 200
    assert b"suspended" in res.data
    assert b"Inappropriate content" in res.data

    # 3. Make request as a logged-in user who just got suspended
    # Let's log Bob in, suspend him, and check that on his next request he gets logged out.
    login("bob@example.com")
    # Bob is logged in now. Let's suspend Bob directly via repository/service.
    with app.app_context():
        UserRepository().update_status(setup_users["bob"].id, "suspended", datetime.utcnow() + timedelta(days=2), "Test Bob Suspend")

    # Now make a request as Bob (e.g. view dashboard)
    res = client.get("/dashboard", follow_redirects=True)
    assert res.status_code == 200
    # Bob should be logged out and redirected to login with flash message
    assert b"suspended" in res.data
    assert b"Test Bob Suspend" in res.data
    # Verify Bob is indeed logged out
    res = client.get("/dashboard")
    assert res.status_code == 302
    assert "/auth/login" in res.headers["Location"]


def test_user_suspension_auto_expiry(app, client, login, setup_users):
    # Suspend user with expired time
    with app.app_context():
        expired_time = datetime.utcnow() - timedelta(minutes=1)
        UserRepository().update_status(setup_users["bob"].id, "suspended", expired_time, "Expired suspension")

    # Log in as Bob. Authentication should automatically lift suspension.
    res = client.post(
        "/auth/login",
        data={"email": "bob@example.com", "password": "Password123!"},
        follow_redirects=True
    )
    assert res.status_code == 200
    assert b"Welcome back" in res.data

    # Verify status is restored to active in DB
    with app.app_context():
        user = UserRepository().find_by_id(setup_users["bob"].id)
        assert user.status == "active"
        assert user.suspended_until is None
        assert user.suspension_reason is None


def test_user_permanent_ban_flow(app, client, login, setup_users):
    # 1. Admin bans Alice
    login("admin@example.com")
    res = client.post(
        f"/admin/users/{setup_users['alice'].id}/ban",
        data={"reason": "Scam activity"},
        follow_redirects=True
    )
    assert res.status_code == 200
    assert b"permanently banned" in res.data

    with app.app_context():
        # Verify status is banned
        user = UserRepository().find_by_id(setup_users["alice"].id)
        assert user.status == "banned"
        assert user.suspension_reason == "Scam activity"

        # Verify active listing is deactivated
        listings = SkillRepository().find_by_user_id(setup_users["alice"].id)
        assert len(listings) == 1
        assert listings[0].status == "deactivated"

        # Verify audit log
        db = Database()
        audit = db.fetch_one("SELECT * FROM admin_audit_logs WHERE action = 'ban_user' ORDER BY created_at DESC")
        assert audit is not None
        assert "Permanently banned" in audit["detail"]
        db.close()

    # 2. Try to log in as banned user
    client.get("/auth/logout")
    res = client.post(
        "/auth/login",
        data={"email": "alice@example.com", "password": "Password123!"},
        follow_redirects=True
    )
    assert res.status_code == 200
    assert b"permanently banned" in res.data
    assert b"Scam activity" in res.data


def test_lift_restrictions(app, client, login, setup_users):
    # Suspend user
    with app.app_context():
        UserRepository().update_status(setup_users["bob"].id, "suspended", datetime.utcnow() + timedelta(days=2), "Suspend")

    # Admin lifts restriction
    login("admin@example.com")
    res = client.post(f"/admin/users/{setup_users['bob'].id}/unsuspend", follow_redirects=True)
    assert res.status_code == 200
    assert b"restriction has been lifted" in res.data

    with app.app_context():
        # Verify status is active
        user = UserRepository().find_by_id(setup_users["bob"].id)
        assert user.status == "active"
        assert user.suspended_until is None

        # Verify audit log
        db = Database()
        audit = db.fetch_one("SELECT * FROM admin_audit_logs WHERE action = 'unsuspend_user' ORDER BY created_at DESC")
        assert audit is not None
        assert "Unsuspended / unbanned" in audit["detail"]
        db.close()
