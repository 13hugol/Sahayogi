from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

from app.database import Database
from app.services import ProfileService


def test_top_rated_users_filtering_and_ordering(app, user_factory):
    # Setup test database records
    with app.app_context():
        # User 1: 4 reviews, 4.8 rating, offered skill is Tech (Python)
        u1 = user_factory(full_name="User One", email="u1@example.com")
        _update_profile(u1.id, reputation_score=4.8, review_count=4, completed_exchange_count=5, headline="Tech expert")
        _add_offered_skill(u1.id, "Python coding")
        
        # User 2: 3 reviews, 4.9 rating, offered skill is Music (Guitar)
        u2 = user_factory(full_name="User Two", email="u2@example.com")
        _update_profile(u2.id, reputation_score=4.9, review_count=3, completed_exchange_count=3, headline="Guitar tutor")
        _add_offered_skill(u2.id, "Guitar lessons")
        
        # User 3: 2 reviews (not eligible), 5.0 rating
        u3 = user_factory(full_name="User Three", email="u3@example.com")
        _update_profile(u3.id, reputation_score=5.0, review_count=2, completed_exchange_count=2)
        _add_offered_skill(u3.id, "Cooking")
        
        # Resolve services
        profile_service = app.view_functions["reviews.top_rated"].__self__._profile_service
        results = profile_service.get_top_rated_profiles(limit=10)
        
        assert len(results) == 2
        # Ordered by reputation score desc: User Two (4.9) then User One (4.8)
        assert results[0].full_name == "User Two"
        assert results[0].reputation_score == 4.9
        assert results[0].top_category_name == "Music"
        
        assert results[1].full_name == "User One"
        assert results[1].reputation_score == 4.8
        assert results[1].top_category_name == "Tech"


def test_top_rated_daily_cache_refresh(app, user_factory):
    with app.app_context():
        # Setup at least one eligible user
        u = user_factory(full_name="Cache User", email="cache@example.com")
        _update_profile(u.id, reputation_score=4.5, review_count=3, completed_exchange_count=3)
        _add_offered_skill(u.id, "Momo cooking")
        
        profile_service = app.view_functions["reviews.top_rated"].__self__._profile_service
        
        # Clear static cache first
        ProfileService._top_rated_cache = None
        ProfileService._top_rated_cache_time = None
        
        # We temporarily mock TESTING config as False to activate caching
        with patch.dict(app.config, {"TESTING": False}):
            res1 = profile_service.get_top_rated_profiles()
            assert len(res1) == 1
            
            # Change reputation score directly in database, bypassing service
            _update_reputation_score(u.id, 5.0)
            
            # Fetch again. Since it is cached, it should return res1 (reputation 4.5)
            res2 = profile_service.get_top_rated_profiles()
            assert res2[0].reputation_score == 4.5
            
            # Fast-forward cache time by 1 day
            ProfileService._top_rated_cache_time = datetime.now() - timedelta(days=1, seconds=10)
            
            # Fetch again. Cache should expire and reload new data (reputation 5.0)
            res3 = profile_service.get_top_rated_profiles()
            assert res3[0].reputation_score == 5.0


def _update_profile(user_id, reputation_score, review_count, completed_exchange_count, headline=None):
    db = Database()
    try:
        db.execute(
            """
            UPDATE profiles
            SET reputation_score = %s,
                review_count = %s,
                completed_exchange_count = %s,
                headline = %s
            WHERE user_id = %s
            """,
            (reputation_score, review_count, completed_exchange_count, headline, user_id),
        )
    finally:
        db.close()


def _update_reputation_score(user_id, score):
    db = Database()
    try:
        db.execute("UPDATE profiles SET reputation_score = %s WHERE user_id = %s", (score, user_id))
    finally:
        db.close()


def _add_offered_skill(user_id, skill_name):
    db = Database()
    try:
        db.execute(
            """
            INSERT INTO profile_skills (user_id, skill_name, skill_type)
            VALUES (%s, %s, 'offered')
            """,
            (user_id, skill_name),
        )
    finally:
        db.close()
