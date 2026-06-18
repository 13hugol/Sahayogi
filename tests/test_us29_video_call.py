from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from app.database import Database
from app.models.user import User
from app.repositories import ExchangeRepository, ExchangeRequestRepository, UserRepository, MessageRepository


@pytest.fixture()
def exchange_setup(app, user_factory):
    with app.app_context():
        teacher = user_factory(email="teacher@example.com", full_name="Alice Teacher")
        learner = user_factory(email="learner@example.com", full_name="Bob Learner")

        with Database() as db:
            cat_row = db.fetch_one("SELECT id FROM categories WHERE name = %s", ("Music",))
            if cat_row:
                cat_id = cat_row["id"]
            else:
                cat_id = db.execute(
                    "INSERT INTO categories (name, description) VALUES (%s, %s)",
                    ("Music", "Music skills"),
                )
            ps_id = db.execute(
                "INSERT INTO profile_skills (user_id, skill_name, skill_type) VALUES (%s, %s, 'offered')",
                (teacher.id, "Guitar"),
            )
            listing_id = db.execute(
                """
                INSERT INTO skills (user_id, category_id, skill_id, title, description, exchange_type, credit_cost, availability, location_text, contact_method, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'approved')
                """,
                (teacher.id, cat_id, ps_id, "Guitar for Beginners", "Learn acoustic guitar.", "credit", 20, "Weekends", "Kathmandu", "Platform"),
            )
        return {"teacher": teacher, "learner": learner, "listing_id": listing_id}


def _create_accepted_exchange(app, client, login, exchange_setup):
    login("learner@example.com")
    client.post(
        f"/requests/create/{exchange_setup['listing_id']}",
        data={"requested_message": "Guitar basics please."},
        follow_redirects=True,
    )
    with app.app_context():
        reqs = ExchangeRequestRepository().list_sent(exchange_setup["learner"].id)
        req_id = reqs[0].id

    client.get("/auth/logout", follow_redirects=True)
    login("teacher@example.com")
    client.post(f"/requests/{req_id}/accept", follow_redirects=True)

    with app.app_context():
        exchange = ExchangeRepository().find_by_request_id(req_id)
    return exchange


def test_online_status_detection(app, user_factory):
    with app.app_context():
        user = user_factory(email="test_status@example.com")
        
        # Manually update active timestamp to now
        with Database() as db:
            db.execute("UPDATE users SET last_active_at = %s WHERE id = %s", (datetime.utcnow(), user.id))
        
        user_loaded = UserRepository().find_by_id(user.id)
        assert user_loaded.is_online is True

        # Manually update active timestamp to 3 minutes ago
        three_mins_ago = datetime.utcnow() - timedelta(minutes=3)
        with Database() as db:
            db.execute("UPDATE users SET last_active_at = %s WHERE id = %s", (three_mins_ago, user.id))
            
        user_loaded = UserRepository().find_by_id(user.id)
        assert user_loaded.is_online is False


def test_video_call_initiation_posts_message_and_requires_both_online(app, client, login, exchange_setup):
    exchange = _create_accepted_exchange(app, client, login, exchange_setup)

    # 1. Attempt to start video call when participants are offline
    # We manually set the learner's last_active_at to 5 minutes ago to ensure they are offline
    with app.app_context():
        five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
        with Database() as db:
            db.execute("UPDATE users SET last_active_at = %s WHERE id = %s", (five_mins_ago, exchange_setup["learner"].id))

    login("teacher@example.com")
    res = client.post(f"/exchanges/{exchange.id}/video/start", follow_redirects=True)
    assert b"must be online to start a video call" in res.data

    # 2. Mark both online
    with app.app_context():
        with Database() as db:
            db.execute("UPDATE users SET last_active_at = %s WHERE id IN (%s, %s)", 
                       (datetime.utcnow(), exchange_setup["teacher"].id, exchange_setup["learner"].id))

    res = client.post(f"/exchanges/{exchange.id}/video/start", follow_redirects=True)
    assert res.status_code == 200
    assert b"Live Learning Room" in res.data
    assert b"Video Call" in res.data

    # Verify call status in Database
    with app.app_context():
        ex = ExchangeRepository().find_by_id(exchange.id)
        assert ex.video_call_active is True
        assert ex.video_call_started_at is not None

        # Verify system message posted
        conv = ex.conversation
        messages = MessageRepository().list_messages(conv.id)
        assert any("Video call started" in m.body for m in messages)


def test_video_call_termination_logs_summary(app, client, login, exchange_setup):
    exchange = _create_accepted_exchange(app, client, login, exchange_setup)

    # Mark both online and start call
    with app.app_context():
        with Database() as db:
            db.execute("UPDATE users SET last_active_at = %s WHERE id IN (%s, %s)", 
                       (datetime.utcnow(), exchange_setup["teacher"].id, exchange_setup["learner"].id))

    login("teacher@example.com")
    client.post(f"/exchanges/{exchange.id}/video/start", follow_redirects=True)

    # Manually backdate start time to 5 minutes ago to simulate call duration
    five_mins_ago = datetime.utcnow() - timedelta(minutes=5)
    with app.app_context():
        with Database() as db:
            db.execute("UPDATE exchanges SET video_call_started_at = %s WHERE id = %s", (five_mins_ago, exchange.id))

    # Terminate call
    res = client.post(f"/exchanges/{exchange.id}/video/end", follow_redirects=True)
    assert res.status_code == 200
    assert b"Video call ended" in res.data

    # Verify details in DB
    with app.app_context():
        ex = ExchangeRepository().find_by_id(exchange.id)
        assert ex.video_call_active is False
        assert "Duration:" in ex.video_session_summary
        assert "Participants: Bob Learner and Alice Teacher" in ex.video_session_summary
        
        # Verify message posted
        conv = ex.conversation
        messages = MessageRepository().list_messages(conv.id)
        assert any("Video call ended. Duration:" in m.body for m in messages)


def test_video_call_heartbeat(app, client, login, exchange_setup):
    exchange = _create_accepted_exchange(app, client, login, exchange_setup)

    login("teacher@example.com")
    res = client.post(f"/exchanges/{exchange.id}/video/heartbeat")
    assert res.status_code == 200
    data = res.get_json()
    assert "other_online" in data
    assert "video_call_active" in data
    assert "summary" in data


def test_video_call_auth_protection(app, client, login, exchange_setup, user_factory):
    exchange = _create_accepted_exchange(app, client, login, exchange_setup)

    # Log in as unrelated user
    client.get("/auth/logout", follow_redirects=True)
    with app.app_context():
        third_user = user_factory(email="unrelated@example.com")
    login("unrelated@example.com")

    res = client.get(f"/exchanges/{exchange.id}/video")
    assert res.status_code == 403

    res = client.post(f"/exchanges/{exchange.id}/video/start")
    assert res.status_code == 403

    res = client.post(f"/exchanges/{exchange.id}/video/end")
    assert res.status_code == 403
