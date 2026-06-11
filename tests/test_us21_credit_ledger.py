from __future__ import annotations

import pytest
from app.database import Database
from app.models.exchange_request import ExchangeRequest
from app.models.exchange import Exchange
from app.repositories import ExchangeRequestRepository, ExchangeRepository, UserRepository, CreditRepository


@pytest.fixture()
def setup_credit_listing(app, user_factory):
    with app.app_context():
        teacher = user_factory(email="teacher@example.com", full_name="Alice Teacher")
        learner = user_factory(email="learner@example.com", full_name="Bob Learner")
        
        # Set teacher's credit balance to 50, learner's credit balance to 100
        db = Database()
        db.execute("UPDATE users SET credit_balance = 50 WHERE id = %s", (teacher.id,))
        db.execute("UPDATE users SET credit_balance = 100 WHERE id = %s", (learner.id,))
        
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
            (teacher.id, cat_id, ps_id, "Guitar for Beginners", "Learn to play acoustic guitar.", "credit", 20, "Weekends", "Kathmandu", "Platform")
        )
        
        db.close()
        return {
            "teacher": teacher,
            "learner": learner,
            "listing_id": listing_id,
        }


def test_initial_credits_and_insufficient_validation(app, client, login, setup_credit_listing):
    with app.app_context():
        t_user = UserRepository().find_by_id(setup_credit_listing["teacher"].id)
        l_user = UserRepository().find_by_id(setup_credit_listing["learner"].id)
        assert t_user.available_credit_balance == 50
        assert l_user.available_credit_balance == 100

    login("learner@example.com")
    with app.app_context():
        db = Database()
        db.execute("UPDATE users SET credit_balance = 10 WHERE id = %s", (setup_credit_listing["learner"].id,))
        db.close()

    res = client.post(
        f"/requests/create/{setup_credit_listing['listing_id']}",
        data={"requested_message": "Guitar basics please."},
        follow_redirects=True
    )
    assert res.status_code == 200
    assert b"insufficient" in res.data.lower()


def test_request_creates_hold_and_release_on_decline(app, client, login, setup_credit_listing):
    login("learner@example.com")

    res = client.post(
        f"/requests/create/{setup_credit_listing['listing_id']}",
        data={"requested_message": "Guitar basics please."},
        follow_redirects=True
    )
    assert res.status_code == 200
    assert b"submitted" in res.data.lower()

    with app.app_context():
        l_user = UserRepository().find_by_id(setup_credit_listing["learner"].id)
        assert l_user.credit_balance == 100
        assert l_user.available_credit_balance == 80

        holds = CreditRepository().get_active_holds_for_user(l_user.id)
        assert len(holds) == 1
        hold = holds[0]
        assert hold.amount == 20
        assert hold.status == "active"

        reqs = ExchangeRequestRepository().list_sent(l_user.id)
        req_id = reqs[0].id

    client.get("/auth/logout", follow_redirects=True)
    login("teacher@example.com")
    res = client.post(
        f"/requests/{req_id}/decline",
        data={"decline_reason": "No time"},
        follow_redirects=True
    )
    assert res.status_code == 200

    with app.app_context():
        l_user = UserRepository().find_by_id(setup_credit_listing["learner"].id)
        assert l_user.available_credit_balance == 100

        holds = CreditRepository().get_active_holds_for_user(l_user.id)
        assert len(holds) == 0


def test_request_creates_hold_and_release_on_cancel(app, client, login, setup_credit_listing):
    login("learner@example.com")

    res = client.post(
        f"/requests/create/{setup_credit_listing['listing_id']}",
        data={"requested_message": "Guitar basics please."},
        follow_redirects=True
    )
    assert res.status_code == 200

    with app.app_context():
        l_user = UserRepository().find_by_id(setup_credit_listing["learner"].id)
        assert l_user.available_credit_balance == 80
        reqs = ExchangeRequestRepository().list_sent(l_user.id)
        req_id = reqs[0].id

    res = client.post(f"/requests/{req_id}/cancel", follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        l_user = UserRepository().find_by_id(setup_credit_listing["learner"].id)
        assert l_user.available_credit_balance == 100


def test_exchange_completion_credit_transfer(app, client, login, setup_credit_listing):
    login("learner@example.com")

    client.post(
        f"/requests/create/{setup_credit_listing['listing_id']}",
        data={"requested_message": "Guitar basics please."},
        follow_redirects=True
    )

    with app.app_context():
        l_user = UserRepository().find_by_id(setup_credit_listing["learner"].id)
        reqs = ExchangeRequestRepository().list_sent(l_user.id)
        req_id = reqs[0].id

    client.get("/auth/logout", follow_redirects=True)
    login("teacher@example.com")
    client.post(f"/requests/{req_id}/accept", follow_redirects=True)

    with app.app_context():
        exchange = ExchangeRepository().find_by_request_id(req_id)
        assert exchange is not None
        assert exchange.status == "active"

    res = client.post(f"/exchanges/{exchange.id}/complete", follow_redirects=True)
    assert res.status_code == 200
    assert b"completed successfully" in res.data.lower()

    with app.app_context():
        updated_exchange = ExchangeRepository().find_by_id(exchange.id)
        assert updated_exchange.status == "completed"

        learner = UserRepository().find_by_id(setup_credit_listing["learner"].id)
        assert learner.credit_balance == 80
        assert learner.available_credit_balance == 80

        teacher = UserRepository().find_by_id(setup_credit_listing["teacher"].id)
        assert teacher.credit_balance == 70
        assert teacher.available_credit_balance == 70

        holds = CreditRepository().get_active_holds_for_user(learner.id)
        assert len(holds) == 0

        l_txs = CreditRepository().get_history_for_user(learner.id)
        assert len(l_txs) == 1
        l_tx = l_txs[0]
        assert l_tx.amount_delta == -20
        assert l_tx.entry_type == "deduction"
        assert "Spent on learning" in l_tx.description

        t_txs = CreditRepository().get_history_for_user(teacher.id)
        assert len(t_txs) == 1
        t_tx = t_txs[0]
        assert t_tx.amount_delta == 20
        assert t_tx.entry_type == "earning"
        assert "Earned from teaching" in t_tx.description
