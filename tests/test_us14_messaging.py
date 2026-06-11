from __future__ import annotations

import pytest

from app.database import Database
from app.repositories import MessageRepository
from app.services import MessageService


def test_messaging_requires_accepted_exchange_or_match(app, user_factory):
    with app.app_context():
        user_a = user_factory(email="message-a@example.com")
        user_b = user_factory(email="message-b@example.com")
        service = MessageService(MessageRepository())

        with pytest.raises(ValueError, match="accepted exchange or mutual match"):
            service.create_conversation(
                subject="Invalid contact",
                permission_source="listing_contact",
                participant_ids=[user_a.id, user_b.id],
            )

        conversation = service.create_conversation(
            subject="Accepted exchange: Python for Guitar",
            permission_source="accepted_exchange",
            participant_ids=[user_a.id, user_b.id],
        )

        assert conversation.id is not None
        assert conversation.permission_source == "accepted_exchange"


def test_conversation_list_and_send_message(app, client, login, user_factory):
    with app.app_context():
        sender = user_factory(email="sender@example.com")
        recipient = user_factory(email="recipient@example.com")
        conversation = MessageService(MessageRepository()).create_conversation(
            subject="Accepted exchange: Python for Guitar",
            permission_source="accepted_exchange",
            participant_ids=[sender.id, recipient.id],
        )

    login("sender@example.com")
    inbox = client.get("/messages/")

    assert inbox.status_code == 200
    assert b"Conversations" in inbox.data
    assert b"Accepted exchange: Python for Guitar" in inbox.data
    assert b"With Test Member" in inbox.data
    assert b"Write your message" in inbox.data

    response = client.post(
        f"/messages/{conversation.id}",
        data={"body": "Hello exchange partner, here is my first message."},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Message sent" in response.data
    assert b"Hello exchange partner" in response.data
    assert b"Delivered" in response.data

    with app.app_context():
        db = Database()
        try:
            row = db.fetch_one(
                "SELECT body, delivered_at, read_at FROM message_posts WHERE conversation_id = %s",
                (conversation.id,),
            )
        finally:
            db.close()

    assert row["body"] == "Hello exchange partner, here is my first message."
    assert row["delivered_at"] is not None
    assert row["read_at"] is None


def test_opening_conversation_marks_incoming_messages_read(app, client, login, user_factory):
    with app.app_context():
        sender = user_factory(email="read-sender@example.com")
        recipient = user_factory(email="read-recipient@example.com")
        service = MessageService(MessageRepository())
        conversation = service.create_conversation(
            subject="Mutual match: Language practice",
            permission_source="match",
            participant_ids=[sender.id, recipient.id],
        )
        service.send_message(
            conversation_id=conversation.id,
            sender_id=sender.id,
            body="Can we practise Nepali conversation this week?",
        )

    login("read-recipient@example.com")
    response = client.get(f"/messages/{conversation.id}")

    assert response.status_code == 200
    assert b"Can we practise Nepali conversation" in response.data

    with app.app_context():
        db = Database()
        try:
            row = db.fetch_one(
                "SELECT read_at FROM message_posts WHERE conversation_id = %s",
                (conversation.id,),
            )
        finally:
            db.close()

    assert row["read_at"] is not None

    client.get("/auth/logout", follow_redirects=True)
    login("read-sender@example.com")
    sender_view = client.get(f"/messages/{conversation.id}")

    assert b"Read" in sender_view.data


def test_message_body_limit_and_participant_access(app, client, login, user_factory):
    with app.app_context():
        sender = user_factory(email="limit-sender@example.com")
        recipient = user_factory(email="limit-recipient@example.com")
        outsider = user_factory(email="outsider@example.com")
        conversation = MessageService(MessageRepository()).create_conversation(
            subject="Accepted exchange: Limit check",
            permission_source="accepted_exchange",
            participant_ids=[sender.id, recipient.id],
        )

    login("limit-sender@example.com")
    too_long = "x" * 2001
    response = client.post(
        f"/messages/{conversation.id}",
        data={"body": too_long},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"2000 characters or fewer" in response.data

    with app.app_context():
        db = Database()
        try:
            row = db.fetch_one(
                "SELECT COUNT(*) AS count FROM message_posts WHERE conversation_id = %s",
                (conversation.id,),
            )
        finally:
            db.close()

    assert row["count"] == 0

    client.get("/auth/logout", follow_redirects=True)
    login("outsider@example.com")
    denied = client.get(f"/messages/{conversation.id}")

    assert denied.status_code == 404
