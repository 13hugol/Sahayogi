from __future__ import annotations

from app.models.profile import ProfileReview, get_score_tier
from app.models.user import User

def test_t19_01_user_with_0_reviews(app, user_factory):
    with app.app_context():
        user = user_factory()
        score_data = ProfileReview.get_reputation_score(user.id)
    assert score_data["score"] is None
    assert score_data["count"] == 0

def test_t19_02_user_with_2_reviews(app, user_factory):
    with app.app_context():
        user = user_factory()
        ProfileReview.create(reviewee_user_id=user.id, reviewer_name="Rev1", rating=4)
        ProfileReview.create(reviewee_user_id=user.id, reviewer_name="Rev2", rating=5)
        score_data = ProfileReview.get_reputation_score(user.id)
    assert score_data["score"] is None
    assert score_data["count"] == 2

def test_t19_03_user_with_3_reviews(app, user_factory):
    with app.app_context():
        user = user_factory()
        ProfileReview.create(reviewee_user_id=user.id, reviewer_name="Rev1", rating=4)
        ProfileReview.create(reviewee_user_id=user.id, reviewer_name="Rev2", rating=4)
        ProfileReview.create(reviewee_user_id=user.id, reviewer_name="Rev3", rating=5)
        score_data = ProfileReview.get_reputation_score(user.id)
    assert score_data["score"] == 4.3
    assert score_data["count"] == 3

def test_t19_04_score_rounds_to_1_decimal(app, user_factory):
    with app.app_context():
        user = user_factory()
        ProfileReview.create(reviewee_user_id=user.id, reviewer_name="Rev1", rating=3)
        ProfileReview.create(reviewee_user_id=user.id, reviewer_name="Rev2", rating=4)
        ProfileReview.create(reviewee_user_id=user.id, reviewer_name="Rev3", rating=5)
        score_data = ProfileReview.get_reputation_score(user.id)
    assert score_data["score"] == 4.0

def test_t19_05_score_updates_after_new_review(app, user_factory):
    with app.app_context():
        user = user_factory()
        ProfileReview.create(reviewee_user_id=user.id, reviewer_name="Rev1", rating=4)
        ProfileReview.create(reviewee_user_id=user.id, reviewer_name="Rev2", rating=4)
        ProfileReview.create(reviewee_user_id=user.id, reviewer_name="Rev3", rating=5)
        
        # Add 4th review
        ProfileReview.create(reviewee_user_id=user.id, reviewer_name="Rev4", rating=2)
        
        updated_user = User.find_by_id(user.id)
    assert updated_user.profile.reputation_score == 3.8
    assert updated_user.profile.review_count == 4

def test_t19_06_score_visible_on_profile_route(app, client, user_factory):
    with app.app_context():
        user = user_factory(full_name="Target")
        ProfileReview.create(reviewee_user_id=user.id, reviewer_name="Rev1", rating=4)
        ProfileReview.create(reviewee_user_id=user.id, reviewer_name="Rev2", rating=4)
        ProfileReview.create(reviewee_user_id=user.id, reviewer_name="Rev3", rating=5)
        user_id = user.id

    response = client.get(f"/users/{user_id}")
    html = response.data.decode("utf-8")
    assert "4.3" in html
    assert "reputation-block" in html
    assert "3 reviews" in html

def test_t19_07_new_member_label_on_profile_route(app, client, user_factory):
    with app.app_context():
        user = user_factory(full_name="Target2")
        user_id = user.id

    response = client.get(f"/users/{user_id}")
    html = response.data.decode("utf-8")
    assert "New Member" in html
    assert "reputation-block" in html

def test_t19_08_api_endpoint_returns_json(app, client, login, user_factory):
    with app.app_context():
        user = user_factory()
        viewer = user_factory(email="viewer@test.com")
        ProfileReview.create(reviewee_user_id=user.id, reviewer_name="Rev1", rating=4)
        ProfileReview.create(reviewee_user_id=user.id, reviewer_name="Rev2", rating=5)
        ProfileReview.create(reviewee_user_id=user.id, reviewer_name="Rev3", rating=5)
        user_id = user.id

    login("viewer@test.com")
    response = client.get(f"/api/reputation/{user_id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["score"] == 4.7
    assert data["count"] == 3
    assert data["tier"] == "Trusted"

def test_t19_09_tier_logic(app):
    assert get_score_tier(4.6, 10) == "Top Rated"
    assert get_score_tier(4.5, 10) == "Top Rated"
    assert get_score_tier(4.5, 9) == "Trusted"
    assert get_score_tier(3.5, 5) == "Trusted"
    assert get_score_tier(3.4, 5) == "Member"
    assert get_score_tier(4.0, 2) == "New Member"
    assert get_score_tier(None, 2) == "New Member"

def test_t19_10_unauthenticated_api_access(app, client, user_factory):
    with app.app_context():
        user = user_factory()
        user_id = user.id

    response = client.get(f"/api/reputation/{user_id}")
    assert response.status_code == 302
