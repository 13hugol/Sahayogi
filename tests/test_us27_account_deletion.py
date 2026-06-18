from __future__ import annotations

import os
from pathlib import Path
from flask import current_app
from app.database import Database
from app.models import User, ProfileSkill
from app.repositories import UserRepository, CategoryRepository
from app.enums import SkillType


def test_account_deletion_requires_login(client):
    # Try deleting account without logging in
    res = client.post("/profile/delete", data={"password": "Password123!"})
    assert res.status_code == 302
    assert "/auth/login" in res.headers["Location"]


def test_account_deletion_password_verification(app, client, login, user_factory):
    with app.app_context():
        alice = user_factory(email="alice@example.com", password="CorrectPassword123!")
        alice_id = alice.id

    login("alice@example.com", "CorrectPassword123!")

    # Attempt delete with wrong password
    res = client.post("/profile/delete", data={"password": "WrongPassword!"}, follow_redirects=True)
    assert b"Incorrect password confirmation." in res.data

    with app.app_context():
        # User should still be active and logged in
        user = UserRepository().find_by_id(alice_id)
        assert user.status == "active"


def test_account_deletion_flow_and_anonymization(app, client, login, user_factory):
    with app.app_context():
        # Setup files and database state
        alice = user_factory(email="alice@example.com", password="Password123!", full_name="Alice Member")
        bob = user_factory(email="bob@example.com", password="Password123!", full_name="Bob Member")
        alice_id = alice.id
        bob_id = bob.id

        # Create category
        cat_repo = CategoryRepository()
        tech = cat_repo.ensure("Tech", "Tech skills")

        # Mock avatar file
        upload_folder = current_app.config["UPLOAD_FOLDER"]
        avatar_dir = Path(upload_folder) / "avatars"
        avatar_dir.mkdir(parents=True, exist_ok=True)
        avatar_file = avatar_dir / f"user-{alice_id}-avatar.png"
        avatar_file.write_text("dummy avatar content")

        # Update avatar path in DB
        db = Database()
        db.execute("UPDATE profiles SET avatar_path = %s, bio = 'This is my bio', location = 'Kathmandu' WHERE user_id = %s", (f"avatars/user-{alice_id}-avatar.png", alice_id))

        # Create a listing for Alice
        ps_alice = ProfileSkill.create(alice_id, "Python coding", SkillType.OFFERED)
        db.execute(
            """
            INSERT INTO skills (user_id, category_id, skill_id, title, description, exchange_type, credit_cost, availability, location_text, contact_method, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'approved')
            """,
            (alice_id, tech.id, ps_alice.id, "Alice Python Basics", "Learn Python", "credit", 10, "Daily", "Kathmandu", "Platform")
        )

        # Mock certificate file
        cert_dir = Path(upload_folder) / "certificates"
        cert_dir.mkdir(parents=True, exist_ok=True)
        cert_file = cert_dir / f"cert-{alice_id}.pdf"
        cert_file.write_text("dummy certificate content")
        db.execute("INSERT INTO profile_certificates (user_id, profile_skill_id, skill_name, status, file_path) VALUES (%s, %s, %s, 'approved', %s)", (alice_id, ps_alice.id, "Python coding", f"certificates/cert-{alice_id}.pdf"))

        # Create a message conversation and post a message from Alice to Bob
        conv_id = db.execute("INSERT INTO message_conversations (subject, permission_source) VALUES ('Conversation', 'match')")
        db.execute("INSERT INTO message_participants (conversation_id, user_id) VALUES (%s, %s)", (conv_id, alice_id))
        db.execute("INSERT INTO message_participants (conversation_id, user_id) VALUES (%s, %s)", (conv_id, bob_id))
        db.execute("INSERT INTO message_posts (conversation_id, sender_id, body) VALUES (%s, %s, 'Hello Bob!')", (conv_id, alice_id))

        # Create a review left by Alice for Bob
        db.execute(
            """
            INSERT INTO profile_reviews (reviewee_user_id, reviewer_id, reviewer_name, rating, comment)
            VALUES (%s, %s, %s, 5, 'Great exchange!')
            """,
            (bob_id, alice_id, "Alice Member")
        )

        db.close()

    # Log in as Alice and delete account
    login("alice@example.com", "Password123!")
    res = client.post("/profile/delete", data={"password": "Password123!"}, follow_redirects=True)
    assert b"Your account has been deleted successfully." in res.data

    with app.app_context():
        # 1. Verify files deleted from disk
        assert not avatar_file.exists()
        assert not cert_file.exists()

        # 2. Verify database records updated/deleted
        user = UserRepository().find_by_id(alice_id)
        assert user.status == "deleted"
        assert user.full_name == "Deleted User"
        assert user.email == f"deleted_user_{alice_id}@deleted.invalid"
        assert user.password_hash == ""

        db = Database()
        # Profile cleared
        profile = db.fetch_one("SELECT * FROM profiles WHERE user_id = %s", (alice_id,))
        assert profile["bio"] is None
        assert profile["location"] is None
        assert profile["avatar_path"] is None
        assert profile["username"] == f"deleted_user_{alice_id}"

        # Child tables cleaned up
        assert db.fetch_one("SELECT COUNT(*) AS count FROM skills WHERE user_id = %s", (alice_id,))["count"] == 0
        assert db.fetch_one("SELECT COUNT(*) AS count FROM profile_skills WHERE user_id = %s", (alice_id,))["count"] == 0
        assert db.fetch_one("SELECT COUNT(*) AS count FROM profile_certificates WHERE user_id = %s", (alice_id,))["count"] == 0
        assert db.fetch_one("SELECT COUNT(*) AS count FROM message_posts WHERE sender_id = %s", (alice_id,))["count"] == 0

        # Review left is anonymized
        review = db.fetch_one("SELECT * FROM profile_reviews WHERE reviewee_user_id = %s", (bob_id,))
        assert review["reviewer_id"] is None
        assert review["reviewer_name"] == "Deleted User"

        # 3. Verify confirmation email logged
        mail_log = Path(current_app.config["MAIL_LOG_FILE"])
        assert mail_log.exists()
        log_content = mail_log.read_text()
        assert "TO: alice@example.com" in log_content
        assert "SUBJECT: Account Deletion Confirmed" in log_content

        db.close()


def test_deleted_user_cannot_login_and_session_invalidated(app, client, login, user_factory):
    with app.app_context():
        # Create and delete user
        alice = user_factory(email="alice@example.com", password="Password123!")
        alice_id = alice.id

    login("alice@example.com", "Password123!")
    client.post("/profile/delete", data={"password": "Password123!"})

    # Try logging in again - should fail
    res = login("alice@example.com", "Password123!")
    assert b"Invalid email or password." in res.data or b"Your account" in res.data

    # Try accessing a login-required route
    res = client.get("/profile/edit")
    assert res.status_code == 302
    assert "/auth/login" in res.headers["Location"]
