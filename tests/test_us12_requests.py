from __future__ import annotations

import pytest
from app.database import Database
from app.models.exchange_request import ExchangeRequest
from app.models.exchange import Exchange
from app.models.notification import Notification
from app.repositories import ExchangeRequestRepository, ExchangeRepository, MessageRepository


@pytest.fixture()
def setup_listing(app, user_factory):
    with app.app_context():
        teacher = user_factory(email="teacher@example.com", full_name="Alice Teacher")
        learner = user_factory(email="learner@example.com", full_name="Bob Learner")
        
        # create category and listing directly in database with approved status
        db = Database()
        cat_id = db.execute(
            "INSERT INTO categories (name, description) VALUES (%s, %s)",
            ("Music", "Music skills")
        )
        ps_id = db.execute(
            "INSERT INTO profile_skills (user_id, skill_name, skill_type) VALUES (%s, %s, 'offered')",
            (teacher.id, "Guitar")
        )
        listing_id = db.execute(
            """
            INSERT INTO skills (user_id, category_id, skill_id, title, description, exchange_type, credit_cost, availability, location_text, contact_method, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'approved')
            """,
            (teacher.id, cat_id, ps_id, "Guitar for Beginners", "Learn to play acoustic guitar.", "credit", 10, "Weekends", "Kathmandu", "Platform")
        )
        
        # create a second listing that is expensive to check credit validation
        expensive_listing_id = db.execute(
            """
            INSERT INTO skills (user_id, category_id, skill_id, title, description, exchange_type, credit_cost, availability, location_text, contact_method, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'approved')
            """,
            (teacher.id, cat_id, ps_id, "Advanced Guitar Masterclass", "Pro level lessons.", "credit", 120, "Weekends", "Kathmandu", "Platform")
        )
        
        db.close()
        return {
            "teacher": teacher,
            "learner": learner,
            "listing_id": listing_id,
            "expensive_listing_id": expensive_listing_id,
        }


def test_create_request_validation_and_success(app, client, login, setup_listing):
    # 1. Anonymous user cannot create request
    res = client.post(f"/requests/create/{setup_listing['listing_id']}")
    assert res.status_code == 302
    assert "/auth/login" in res.headers["Location"]

    # Login as learner
    login("learner@example.com")

    # 2. Cannot request own listing
    client.get("/auth/logout", follow_redirects=True)
    login("teacher@example.com")
    res = client.post(
        f"/requests/create/{setup_listing['listing_id']}",
        data={"requested_message": "Can I learn guitar?"},
        follow_redirects=True
    )
    assert res.status_code == 200
    assert b"You cannot request your own listing" in res.data

    client.get("/auth/logout", follow_redirects=True)
    login("learner@example.com")

    # 3. Credit validation check (available credit balance is 100, cost is 120)
    res = client.post(
        f"/requests/create/{setup_listing['expensive_listing_id']}",
        data={"requested_message": "Can I learn advanced guitar?"},
        follow_redirects=True
    )
    assert res.status_code == 200
    assert b"insufficient" in res.data.lower()

    # 4. Successful request creation (cost is 10, balance is 100)
    res = client.post(
        f"/requests/create/{setup_listing['listing_id']}",
        data={"requested_message": "I want to learn guitar basics."},
        follow_redirects=True
    )
    assert res.status_code == 200
    assert b"submitted" in res.data.lower()

    # Verify database state
    with app.app_context():
        sent_reqs = ExchangeRequestRepository().list_sent(setup_listing["learner"].id)
        assert len(sent_reqs) == 1
        req = sent_reqs[0]
        assert req.listing_id == setup_listing["listing_id"]
        assert req.status == "pending"
        assert req.requested_message == "I want to learn guitar basics."
        
        # Verify notification was sent to teacher
        unread_notifs = Notification.get_unread_notifications(setup_listing["teacher"].id)
        assert len(unread_notifs) == 1
        assert "New exchange request" in unread_notifs[0].message


def test_requests_inbox_and_sent_views(app, client, login, setup_listing):
    with app.app_context():
        # create a pending request directly
        req = ExchangeRequestRepository().create(
            listing_id=setup_listing["listing_id"],
            learner_id=setup_listing["learner"].id,
            requested_message="A private message."
        )

    # 1. Test Sent page for learner
    login("learner@example.com")
    res = client.get("/requests/sent")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Guitar for Beginners" in html
    assert "Alice Teacher" in html
    assert "Pending" in html
    assert "A private message" in html

    # Logout and login as teacher
    client.get("/auth/logout", follow_redirects=True)
    login("teacher@example.com")
    
    # 2. Test Request Inbox for teacher
    res = client.get("/requests/inbox")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Bob Learner" in html
    assert "Guitar for Beginners" in html
    assert "A private message" in html
    assert "Accept" in html
    assert "Decline" in html


def test_accept_request_flow(app, client, login, setup_listing):
    with app.app_context():
        # create a pending request
        req = ExchangeRequestRepository().create(
            listing_id=setup_listing["listing_id"],
            learner_id=setup_listing["learner"].id,
            requested_message="Let us start soon!"
        )

    # Non-owner cannot accept the request
    login("learner@example.com")
    res = client.post(f"/requests/{req.id}/accept")
    assert res.status_code == 403

    # Owner (teacher) accepts the request
    client.get("/auth/logout", follow_redirects=True)
    login("teacher@example.com")
    res = client.post(f"/requests/{req.id}/accept", follow_redirects=True)
    assert res.status_code == 200
    assert b"Request accepted and exchange created" in res.data

    # Verify DB state
    with app.app_context():
        # Request status updated
        updated_req = ExchangeRequestRepository().find_by_id(req.id)
        assert updated_req.status == "accepted"
        
        # Exchange created
        exchange = ExchangeRepository().find_by_request_id(req.id)
        assert exchange is not None
        assert exchange.status == "active"
        
        # In-app message conversation opened
        convs = MessageRepository().list_for_user(setup_listing["teacher"].id)
        assert len(convs) == 1
        assert convs[0].permission_source == "accepted_exchange"
        
        # Notification sent to learner
        notifs = Notification.get_unread_notifications(setup_listing["learner"].id)
        assert any("accepted" in n.message.lower() for n in notifs)


def test_decline_request_flow(app, client, login, setup_listing):
    with app.app_context():
        req = ExchangeRequestRepository().create(
            listing_id=setup_listing["listing_id"],
            learner_id=setup_listing["learner"].id,
            requested_message="Let us start soon!"
        )

    # Decline the request as teacher with reason
    login("teacher@example.com")
    res = client.post(
        f"/requests/{req.id}/decline",
        data={"decline_reason": "Sorry, I am fully booked this month."},
        follow_redirects=True
    )
    assert res.status_code == 200
    assert b"Request declined" in res.data

    # Verify DB state
    with app.app_context():
        updated_req = ExchangeRequestRepository().find_by_id(req.id)
        assert updated_req.status == "declined"
        assert updated_req.decline_reason == "Sorry, I am fully booked this month."
        
        # Notification sent to learner includes reason
        notifs = Notification.get_unread_notifications(setup_listing["learner"].id)
        assert any("Sorry, I am fully booked" in n.message for n in notifs)


def test_cancel_request_flow(app, client, login, setup_listing):
    with app.app_context():
        req = ExchangeRequestRepository().create(
            listing_id=setup_listing["listing_id"],
            learner_id=setup_listing["learner"].id,
            requested_message="Please cancel me."
        )

    # Non-learner (teacher) cannot cancel request
    login("teacher@example.com")
    res = client.post(f"/requests/{req.id}/cancel")
    assert res.status_code == 403

    # Learner cancels request
    client.get("/auth/logout", follow_redirects=True)
    login("learner@example.com")
    res = client.post(f"/requests/{req.id}/cancel", follow_redirects=True)
    assert res.status_code == 200
    assert b"Request cancelled" in res.data

    # Verify DB state
    with app.app_context():
        updated_req = ExchangeRequestRepository().find_by_id(req.id)
        assert updated_req.status == "cancelled"
