from __future__ import annotations

import pytest
from app.models.skill import Skill, Category
from app.models.profile import ProfileSkill
from app.repositories import SkillRepository, CategoryRepository
from app.enums import SkillType
from app.database import Database

@pytest.fixture()
def seed_categories(app):
    with app.app_context():
        cat_repo = CategoryRepository()
        tech = cat_repo.ensure("Tech", "Tech skills")
        music = cat_repo.ensure("Music", "Music skills")
        language = cat_repo.ensure("Language", "Language skills")
        kitchen = cat_repo.ensure("Kitchen", "Kitchen skills")
        return {
            "Tech": tech,
            "Music": music,
            "Language": language,
            "Kitchen": kitchen
        }

def test_category_filters(app, client, user_factory, seed_categories):
    with app.app_context():
        user = user_factory(email="alice@example.com")
        ps1 = ProfileSkill.create(user.id, "Python coding", SkillType.OFFERED)
        ps2 = ProfileSkill.create(user.id, "Piano tutorial", SkillType.OFFERED)
        ps3 = ProfileSkill.create(user.id, "Spanish tutor", SkillType.OFFERED)
        
        tech_cat = seed_categories["Tech"]
        music_cat = seed_categories["Music"]
        lang_cat = seed_categories["Language"]

        db = Database()
        db.execute(
            """
            INSERT INTO skills (user_id, category_id, skill_id, title, description, exchange_type, credit_cost, availability, location_text, contact_method, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'approved')
            """,
            (user.id, tech_cat.id, ps1.id, "Python Masterclass", "Learn Python code from scratch.", "credit", 10, "Daily", "Kathmandu", "Platform")
        )
        db.execute(
            """
            INSERT INTO skills (user_id, category_id, skill_id, title, description, exchange_type, credit_cost, availability, location_text, contact_method, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'approved')
            """,
            (user.id, music_cat.id, ps2.id, "Piano Lessons", "Teach kids how to play beautiful melodies.", "teach", 0, "Sunday", "Lalitpur", "Email")
        )
        db.execute(
            """
            INSERT INTO skills (user_id, category_id, skill_id, title, description, exchange_type, credit_cost, availability, location_text, contact_method, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'approved')
            """,
            (user.id, lang_cat.id, ps3.id, "Spanish tutor", "Learn Spanish language.", "teach", 0, "Monday", "Pokhara", "In-app")
        )

    # Search by single category "Tech"
    res = client.get(f"/listings/?category={tech_cat.id}")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Python Masterclass" in html
    assert "Piano Lessons" not in html
    assert "Spanish tutor" not in html

    # Search by multiple categories comma-separated "Tech,Music"
    res = client.get(f"/listings/?category={tech_cat.id},{music_cat.id}")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Python Masterclass" in html
    assert "Piano Lessons" in html
    assert "Spanish tutor" not in html

    # Search by multiple category list parameters
    res = client.get(f"/listings/?category={tech_cat.id}&category={music_cat.id}")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Python Masterclass" in html
    assert "Piano Lessons" in html

    # Combined keyword + category
    res = client.get(f"/listings/?q=Lessons&category={music_cat.id}")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Piano Lessons" in html
    assert "Python Masterclass" not in html

    # API Search returns JSON with correct results
    res = client.get(f"/listings/api/search?category={tech_cat.id},{music_cat.id}")
    assert res.status_code == 200
    data = res.get_json()
    assert data["count"] == 2
    assert "Python Masterclass" in data["html"]
    assert "Piano Lessons" in data["html"]
    assert "Spanish tutor" not in data["html"]


def test_location_radius_filters(app, client, user_factory, seed_categories):
    with app.app_context():
        # Setup users with specific profile locations
        user_kathmandu = user_factory(email="ktm_user@example.com", location="Kathmandu")
        user_pokhara = user_factory(email="pkr_user@example.com", location="Pokhara")

        ps_tech = ProfileSkill.create(user_kathmandu.id, "Python coding", SkillType.OFFERED)
        ps_music = ProfileSkill.create(user_kathmandu.id, "Piano tutorial", SkillType.OFFERED)
        ps_lang = ProfileSkill.create(user_pokhara.id, "Spanish tutor", SkillType.OFFERED)

        tech_cat = seed_categories["Tech"]
        music_cat = seed_categories["Music"]
        lang_cat = seed_categories["Language"]

        db = Database()
        # Listing 1: Kathmandu user, location_text = "Kathmandu" (within Kathmandu, 0 km away)
        db.execute(
            """
            INSERT INTO skills (user_id, category_id, skill_id, title, description, exchange_type, credit_cost, availability, location_text, contact_method, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'approved')
            """,
            (user_kathmandu.id, tech_cat.id, ps_tech.id, "KTM Tech Offer", "Python masterclass in KTM", "credit", 10, "Daily", "Kathmandu", "Platform")
        )
        # Listing 2: Kathmandu user, location_text = "Lalitpur" (~4.8 km away from Kathmandu)
        db.execute(
            """
            INSERT INTO skills (user_id, category_id, skill_id, title, description, exchange_type, credit_cost, availability, location_text, contact_method, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'approved')
            """,
            (user_kathmandu.id, music_cat.id, ps_music.id, "Lalitpur Music Offer", "Piano lessons in Lalitpur", "teach", 0, "Sunday", "Lalitpur", "Email")
        )
        # Listing 3: Pokhara user, location_text = None (falls back to User profile location: Pokhara, ~200 km away from Kathmandu)
        db.execute(
            """
            INSERT INTO skills (user_id, category_id, skill_id, title, description, exchange_type, credit_cost, availability, location_text, contact_method, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'approved')
            """,
            (user_pokhara.id, lang_cat.id, ps_lang.id, "Pokhara Lang Offer", "Spanish tutor in Pokhara", "teach", 0, "Monday", None, "In-app")
        )

    # 1. Search with location=Kathmandu and radius=10
    res = client.get("/listings/?location=Kathmandu&radius=10")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "KTM Tech Offer" in html
    assert "Lalitpur Music Offer" in html
    assert "Pokhara Lang Offer" not in html
    
    # 2. Check that distance is displayed in HTML
    assert "0.0 km away" in html or "0.0 km" in html or "0 km" in html or "away" in html
    assert "4.8 km away" in html

    # 3. Search with location=Kathmandu and radius=50
    res = client.get("/listings/?location=Kathmandu&radius=50")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "KTM Tech Offer" in html
    assert "Lalitpur Music Offer" in html
    assert "Pokhara Lang Offer" not in html

    # 4. Search with location=Kathmandu and radius=empty (Any)
    res = client.get("/listings/?location=Kathmandu")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "KTM Tech Offer" in html
    assert "Lalitpur Music Offer" in html
    assert "Pokhara Lang Offer" in html
    assert "km away" in html

    # 5. Search with coordinates for Kathmandu: 27.7172, 85.3240
    res = client.get("/listings/?location=27.7172,85.3240&radius=10")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "KTM Tech Offer" in html
    assert "Lalitpur Music Offer" in html
    assert "Pokhara Lang Offer" not in html

    # 6. Fuzzy text matching fallback: Search for location that has no coordinates
    with app.app_context():
        user_custom = user_factory(email="custom_user@example.com", location="Custom Village")
        ps_custom = ProfileSkill.create(user_custom.id, "Custom Skill", SkillType.OFFERED)
        db = Database()
        db.execute(
            """
            INSERT INTO skills (user_id, category_id, skill_id, title, description, exchange_type, credit_cost, availability, location_text, contact_method, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'approved')
            """,
            (user_custom.id, tech_cat.id, ps_custom.id, "Custom Location Offer", "Some description here", "credit", 10, "Daily", "Custom Village", "Platform")
        )

    res = client.get("/listings/?location=Custom")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Custom Location Offer" in html
    assert "KTM Tech Offer" not in html
