from __future__ import annotations

import pytest
from app.database import Database
from app.models import User
from app.repositories import MessageRepository, UserRepository


def test_messages_unread_badge_initial_load(app, client, login, user_factory):
    with app.app_context():
        alice = user_factory(email="alice@example.com", password="Password123!")

    login("alice@example.com", "Password123!")
    res = client.get("/profile/me")
    assert res.status_code == 200
    # Sidenav count for messages should have d-none class when count is 0
    assert b'data-count-type="messages">0</b>' in res.data or b'data-count-type="messages"' not in res.data
    assert b'sidenav-count d-none" data-count-type="messages"' in res.data


def test_messages_unread_badge_increments(app, client, login, user_factory):
    with app.app_context():
        alice = user_factory(email="alice@example.com", password="Password123!", full_name="Alice User")
        bob = user_factory(email="bob@example.com", password="Password123!", full_name="Bob User")
        alice_id = alice.id
        bob_id = bob.id

        # Create a message conversation and post an unread message from Bob to Alice
        db = Database()
        conv_id = db.execute("INSERT INTO message_conversations (subject, permission_source) VALUES ('Conversation', 'match')")
        db.execute("INSERT INTO message_participants (conversation_id, user_id) VALUES (%s, %s)", (conv_id, alice_id))
        db.execute("INSERT INTO message_participants (conversation_id, user_id) VALUES (%s, %s)", (conv_id, bob_id))
        db.execute("INSERT INTO message_posts (conversation_id, sender_id, body) VALUES (%s, %s, 'Hello Alice!')", (conv_id, bob_id))
        db.close()

    # Log in as Alice and load page
    login("alice@example.com", "Password123!")
    res = client.get("/profile/me")
    assert res.status_code == 200

    # Badge should show count 1 and not be hidden
    assert b'data-count-type="messages">1</b>' in res.data
    assert b'sidenav-count d-none" data-count-type="messages"' not in res.data


def test_messages_unread_badge_decrements_on_open(app, client, login, user_factory):
    with app.app_context():
        alice = user_factory(email="alice@example.com", password="Password123!", full_name="Alice User")
        bob = user_factory(email="bob@example.com", password="Password123!", full_name="Bob User")
        alice_id = alice.id
        bob_id = bob.id

        db = Database()
        conv_id = db.execute("INSERT INTO message_conversations (subject, permission_source) VALUES ('Conversation', 'match')")
        db.execute("INSERT INTO message_participants (conversation_id, user_id) VALUES (%s, %s)", (conv_id, alice_id))
        db.execute("INSERT INTO message_participants (conversation_id, user_id) VALUES (%s, %s)", (conv_id, bob_id))
        db.execute("INSERT INTO message_posts (conversation_id, sender_id, body) VALUES (%s, %s, 'Hello Alice!')", (conv_id, bob_id))
        db.close()

    # Log in as Alice
    login("alice@example.com", "Password123!")

    # Verify unread count is 1 in DB
    with app.app_context():
        assert MessageRepository().count_unread(alice_id) == 1

    # Open conversation detail
    res = client.get(f"/messages/{conv_id}")
    assert res.status_code == 200

    # Verify unread count is now 0 in DB
    with app.app_context():
        assert MessageRepository().count_unread(alice_id) == 0

    # Refresh page and check that badge is hidden
    res = client.get("/profile/me")
    assert res.status_code == 200
    assert b'data-count-type="messages">0</b>' in res.data or b'data-count-type="messages"' not in res.data
    assert b'sidenav-count d-none" data-count-type="messages"' in res.data


def test_notifications_counts_json_endpoint(app, client, login, user_factory):
    with app.app_context():
        alice = user_factory(email="alice@example.com", password="Password123!", full_name="Alice User")
        bob = user_factory(email="bob@example.com", password="Password123!", full_name="Bob User")
        alice_id = alice.id
        bob_id = bob.id

        db = Database()
        conv_id = db.execute("INSERT INTO message_conversations (subject, permission_source) VALUES ('Conversation', 'match')")
        db.execute("INSERT INTO message_participants (conversation_id, user_id) VALUES (%s, %s)", (conv_id, alice_id))
        db.execute("INSERT INTO message_participants (conversation_id, user_id) VALUES (%s, %s)", (conv_id, bob_id))
        db.execute("INSERT INTO message_posts (conversation_id, sender_id, body) VALUES (%s, %s, 'Hello Alice!')", (conv_id, bob_id))
        db.close()

    login("alice@example.com", "Password123!")
    res = client.get("/notifications/counts", headers={"X-Requested-With": "XMLHttpRequest"})
    assert res.status_code == 200
    data = res.get_json()
    assert "messages" in data
    assert "notifications" in data
    assert data["messages"] == 1
