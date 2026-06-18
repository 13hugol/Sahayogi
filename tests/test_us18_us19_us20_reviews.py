from __future__ import annotations

import pytest

from app.database import Database
from app.repositories import (
    ExchangeRepository,
    ExchangeRequestRepository,
    ProfileReviewRepository,
    UserRepository,
)


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


def _complete_exchange_both_parties(app, client, login, exchange):
    # Currently logged in as teacher after _create_accepted_exchange.
    client.post(f"/exchanges/{exchange.id}/complete", follow_redirects=True)
    client.get("/auth/logout", follow_redirects=True)
    login("learner@example.com")
    client.post(f"/exchanges/{exchange.id}/complete", follow_redirects=True)


def test_review_blocked_until_both_parties_complete(app, client, login, exchange_setup):
    exchange = _create_accepted_exchange(app, client, login, exchange_setup)

    # Only the teacher confirms completion.
    client.post(f"/exchanges/{exchange.id}/complete", follow_redirects=True)

    res = client.get(f"/reviews/exchange/{exchange.id}", follow_redirects=True)
    assert b"unlock after both parties" in res.data.lower()

    res = client.post(
        f"/reviews/exchange/{exchange.id}",
        data={"rating": "5", "comment": "Great"},
        follow_redirects=True,
    )
    assert b"unlock after both parties" in res.data.lower()

    with app.app_context():
        assert ProfileReviewRepository().count_for_user(exchange_setup["learner"].id) == 0


def test_review_submission_updates_reputation_and_notifies(app, client, login, exchange_setup):
    exchange = _create_accepted_exchange(app, client, login, exchange_setup)
    _complete_exchange_both_parties(app, client, login, exchange)

    # Learner reviews the teacher.
    res = client.post(
        f"/reviews/exchange/{exchange.id}",
        data={"rating": "4", "comment": "Patient and well prepared."},
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"review has been published" in res.data.lower()

    teacher_id = exchange_setup["teacher"].id
    with app.app_context():
        reviews = ProfileReviewRepository().for_user(teacher_id)
        assert len(reviews) == 1
        assert reviews[0].rating == 4
        assert reviews[0].exchange_id == exchange.id

        teacher = UserRepository().find_by_id(teacher_id)
        assert teacher.profile.review_count == 1
        assert teacher.profile.reputation_score == 4.0

        db = Database()
        row = db.fetch_one(
            "SELECT COUNT(*) AS count FROM notifications WHERE user_id = %s AND event_type = 'new_review'",
            (teacher_id,),
        )
        db.close()
        assert int(row["count"]) == 1

    # Review is published on the teacher's review history page.
    res = client.get(f"/reviews/users/{teacher_id}")
    assert b"Patient and well prepared." in res.data


def test_one_review_per_completed_exchange(app, client, login, exchange_setup):
    exchange = _create_accepted_exchange(app, client, login, exchange_setup)
    _complete_exchange_both_parties(app, client, login, exchange)

    client.post(
        f"/reviews/exchange/{exchange.id}",
        data={"rating": "5", "comment": "First review."},
        follow_redirects=True,
    )
    res = client.post(
        f"/reviews/exchange/{exchange.id}",
        data={"rating": "1", "comment": "Second attempt."},
        follow_redirects=True,
    )
    assert b"already reviewed" in res.data.lower()

    with app.app_context():
        assert ProfileReviewRepository().count_for_user(exchange_setup["teacher"].id) == 1


def test_review_validation_rules(app, client, login, exchange_setup):
    exchange = _create_accepted_exchange(app, client, login, exchange_setup)
    _complete_exchange_both_parties(app, client, login, exchange)

    res = client.post(
        f"/reviews/exchange/{exchange.id}",
        data={"rating": "9", "comment": "Bad rating"},
        follow_redirects=True,
    )
    assert b"between 1 and 5" in res.data.lower()

    res = client.post(
        f"/reviews/exchange/{exchange.id}",
        data={"rating": "4", "comment": "x" * 501},
        follow_redirects=True,
    )
    assert b"limited to 500 characters" in res.data.lower()

    with app.app_context():
        assert ProfileReviewRepository().count_for_user(exchange_setup["teacher"].id) == 0


def test_reputation_average_and_new_member_display(app, client, login, exchange_setup):
    teacher_id = exchange_setup["teacher"].id
    learner_id = exchange_setup["learner"].id

    with app.app_context():
        repo = ProfileReviewRepository()
        repo.create(reviewee_user_id=teacher_id, reviewer_id=learner_id, reviewer_name="Bob Learner", rating=5)
        repo.create(reviewee_user_id=teacher_id, reviewer_id=learner_id, reviewer_name="Bob Learner", rating=4)
        teacher = UserRepository().find_by_id(teacher_id)
        assert teacher.profile.review_count == 2
        assert teacher.profile.reputation_score == pytest.approx(4.5, abs=0.01)

    # Fewer than 3 reviews: profile shows New Member instead of a numeric score.
    login("learner@example.com")
    res = client.get(f"/users/{teacher_id}")
    assert b"New Member" in res.data

    with app.app_context():
        ProfileReviewRepository().create(
            reviewee_user_id=teacher_id, reviewer_id=learner_id, reviewer_name="Bob Learner", rating=4
        )
        teacher = UserRepository().find_by_id(teacher_id)
        assert teacher.profile.review_count == 3
        assert teacher.profile.reputation_score == pytest.approx(4.3, abs=0.01)

    res = client.get(f"/users/{teacher_id}")
    assert b"New Member" not in res.data
    assert b"4.3" in res.data


def test_review_history_pagination(app, client, login, exchange_setup):
    teacher_id = exchange_setup["teacher"].id
    learner_id = exchange_setup["learner"].id

    with app.app_context():
        repo = ProfileReviewRepository()
        for index in range(12):
            repo.create(
                reviewee_user_id=teacher_id,
                reviewer_id=learner_id,
                reviewer_name="Bob Learner",
                rating=(index % 5) + 1,
                comment=f"Review number {index + 1}",
            )

    login("learner@example.com")
    res = client.get(f"/reviews/users/{teacher_id}")
    assert b"12 reviews received" in res.data
    assert res.data.count(b"Submitted ") == 10
    assert b"Next" in res.data

    res = client.get(f"/reviews/users/{teacher_id}?page=2")
    assert res.data.count(b"Submitted ") == 2


def test_history_dashboard_filters_and_review_button(app, client, login, exchange_setup):
    exchange = _create_accepted_exchange(app, client, login, exchange_setup)
    _complete_exchange_both_parties(app, client, login, exchange)

    # Logged in as learner. Completed exchange appears with a review prompt.
    res = client.get("/exchanges/?status=completed")
    assert b"Guitar for Beginners" in res.data
    assert b"Leave a review" in res.data
    assert b"View listing" in res.data
    assert b"Open chat" in res.data

    res = client.get("/exchanges/?status=active")
    assert b"Guitar for Beginners" not in res.data

    res = client.get("/exchanges/?date_from=2099-01-01")
    assert b"Guitar for Beginners" not in res.data

    res = client.get("/exchanges/?date_to=2000-01-01")
    assert b"Guitar for Beginners" not in res.data

    # After reviewing, the prompt disappears for this user.
    client.post(
        f"/reviews/exchange/{exchange.id}",
        data={"rating": "5", "comment": "Great session."},
        follow_redirects=True,
    )
    res = client.get("/exchanges/?status=completed")
    assert b"Leave a review" not in res.data


def test_completed_exchange_count_increments_for_both(app, client, login, exchange_setup):
    exchange = _create_accepted_exchange(app, client, login, exchange_setup)
    _complete_exchange_both_parties(app, client, login, exchange)

    with app.app_context():
        teacher = UserRepository().find_by_id(exchange_setup["teacher"].id)
        learner = UserRepository().find_by_id(exchange_setup["learner"].id)
        assert teacher.profile.completed_exchange_count == 1
        assert learner.profile.completed_exchange_count == 1
