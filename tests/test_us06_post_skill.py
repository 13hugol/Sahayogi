from __future__ import annotations

import pytest
from app.models.profile import ProfileSkill
from app.models.skill import Skill, Category
from app.repositories import SkillRepository, CategoryRepository
from app.enums import SkillType


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


def test_anonymous_user_listings_redirection(client):
    # Anonymous users should be redirected or block listings actions
    # Create listing redirect
    res = client.get("/listings/create")
    assert res.status_code == 302
    assert "/auth/login" in res.headers["Location"]

    # Mine listings redirect
    res = client.get("/listings/mine")
    assert res.status_code == 302
    assert "/auth/login" in res.headers["Location"]

    # Edit listing redirect
    res = client.get("/listings/1/edit")
    assert res.status_code == 302
    assert "/auth/login" in res.headers["Location"]

    # Delete listing redirect
    res = client.post("/listings/1/delete")
    assert res.status_code == 302
    assert "/auth/login" in res.headers["Location"]


def test_post_listing_form_rendering(app, client, login, user_factory, seed_categories):
    with app.app_context():
        user = user_factory(email="alice@example.com")
        # Add offered skill to profile
        ps1 = ProfileSkill.create(user.id, "Python coding", SkillType.OFFERED)
        ps2 = ProfileSkill.create(user.id, "Guitar tutoring", SkillType.OFFERED)
        # Add wanted skill to profile (should not be in listing choices)
        ps3 = ProfileSkill.create(user.id, "Spanish lessons", SkillType.WANTED)

    login("alice@example.com")
    res = client.get("/listings/create")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Python coding" in html
    assert "Guitar tutoring" in html
    assert "Spanish lessons" not in html


def test_post_listing_validation_failures(app, client, login, user_factory, seed_categories):
    with app.app_context():
        user = user_factory(email="alice@example.com")
        ps1 = ProfileSkill.create(user.id, "Python coding", SkillType.OFFERED)
        tech_cat_id = seed_categories["Tech"].id

    login("alice@example.com")

    # 1. Title too short (<5 chars) and description too short (<10 chars)
    res = client.post("/listings/create", data={
        "title": "Py",
        "description": "short",
        "exchange_type": "credit",
        "skill_id": str(ps1.id),
        "category_id": str(tech_cat_id),
        "min_credits": "10",
        "location_text": "Kathmandu",
        "contact_method": "In-app message",
        "availability_labels": "Weekends 9am-12pm"
    }, follow_redirects=True)
    html = res.data.decode("utf-8")
    assert "Title must be between 5 and 120 characters." in html
    assert "Description must be at least 10 characters." in html

    # 2. Invalid skill_id (not owned by user)
    res = client.post("/listings/create", data={
        "title": "Valid Python mentor offer",
        "description": "Let us learn Python together with step-by-step guides.",
        "exchange_type": "credit",
        "skill_id": "9999",  # Invalid ID
        "category_id": str(tech_cat_id),
        "min_credits": "10",
        "location_text": "Kathmandu",
        "contact_method": "In-app message",
        "availability_labels": "Weekends 9am-12pm"
    }, follow_redirects=True)
    html = res.data.decode("utf-8")
    assert "Please select a valid skill from your profile." in html

    # 3. Invalid category_id
    res = client.post("/listings/create", data={
        "title": "Valid Python mentor offer",
        "description": "Let us learn Python together with step-by-step guides.",
        "exchange_type": "credit",
        "skill_id": str(ps1.id),
        "category_id": "9999",  # Invalid Category
        "min_credits": "10",
        "location_text": "Kathmandu",
        "contact_method": "In-app message",
        "availability_labels": "Weekends 9am-12pm"
    }, follow_redirects=True)
    html = res.data.decode("utf-8")
    assert "Please select a valid category." in html

    # 4. Invalid exchange type
    res = client.post("/listings/create", data={
        "title": "Valid Python mentor offer",
        "description": "Let us learn Python together with step-by-step guides.",
        "exchange_type": "invalid_type",
        "skill_id": str(ps1.id),
        "category_id": str(tech_cat_id),
        "min_credits": "10",
        "location_text": "Kathmandu",
        "contact_method": "In-app message",
        "availability_labels": "Weekends 9am-12pm"
    }, follow_redirects=True)
    html = res.data.decode("utf-8")
    assert "Please select a valid exchange type." in html

    # 5. Invalid credits (negative or non-numeric)
    res = client.post("/listings/create", data={
        "title": "Valid Python mentor offer",
        "description": "Let us learn Python together with step-by-step guides.",
        "exchange_type": "credit",
        "skill_id": str(ps1.id),
        "category_id": str(tech_cat_id),
        "min_credits": "-5",
        "location_text": "Kathmandu",
        "contact_method": "In-app message",
        "availability_labels": "Weekends 9am-12pm"
    }, follow_redirects=True)
    html = res.data.decode("utf-8")
    assert "Credits cannot be negative." in html

    res = client.post("/listings/create", data={
        "title": "Valid Python mentor offer",
        "description": "Let us learn Python together with step-by-step guides.",
        "exchange_type": "credit",
        "skill_id": str(ps1.id),
        "category_id": str(tech_cat_id),
        "min_credits": "abc",
        "location_text": "Kathmandu",
        "contact_method": "In-app message",
        "availability_labels": "Weekends 9am-12pm"
    }, follow_redirects=True)
    html = res.data.decode("utf-8")
    assert "Please enter a valid number of credits." in html

    # 6. Missing availability
    res = client.post("/listings/create", data={
        "title": "Valid Python mentor offer",
        "description": "Let us learn Python together with step-by-step guides.",
        "exchange_type": "credit",
        "skill_id": str(ps1.id),
        "category_id": str(tech_cat_id),
        "min_credits": "10",
        "location_text": "Kathmandu",
        "contact_method": "In-app message",
        "availability_labels": ""  # Missing
    }, follow_redirects=True)
    html = res.data.decode("utf-8")
    assert "Please provide availability details." in html


def test_post_listing_success_and_lifecycle(app, client, login, user_factory, seed_categories):
    with app.app_context():
        user = user_factory(email="alice@example.com")
        ps1 = ProfileSkill.create(user.id, "Python coding", SkillType.OFFERED)
        tech_cat = seed_categories["Tech"]

    login("alice@example.com")

    # Post listing successfully
    res = client.post("/listings/create", data={
        "title": "Learn Python step by step",
        "description": "I will teach you the fundamentals of Python programming.",
        "exchange_type": "credit",
        "skill_id": str(ps1.id),
        "category_id": str(tech_cat.id),
        "min_credits": "15",
        "location_text": "Kathmandu",
        "contact_method": "In-app messaging",
        "availability_labels": "Weekends only\nEvening sessions"
    }, follow_redirects=True)

    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Listing submitted successfully and is pending admin review." in html
    assert "Learn Python step by step" in html
    assert "pending" in html.lower()

    # Get listing from database to verify values
    with app.app_context():
        listings = Skill.find_by_user_id(user.id)
        assert len(listings) == 1
        listing = listings[0]
        assert listing.title == "Learn Python step by step"
        assert listing.description == "I will teach you the fundamentals of Python programming."
        assert listing.exchange_type == "credit"
        assert listing.credit_cost == 15
        assert listing.location_text == "Kathmandu"
        assert listing.contact_method == "In-app messaging"
        assert listing.status == "pending"
        # Check parsed availability list
        avail = listing.availability
        assert len(avail) == 2
        assert avail[0].label == "Weekends only"
        assert avail[1].label == "Evening sessions"

    # Detail page of pending listing should load
    res = client.get(f"/listings/{listing.id}")
    assert res.status_code == 200
    detail_html = res.data.decode("utf-8")
    assert "Learn Python step by step" in detail_html
    assert "Weekends only" in detail_html
    assert "Evening sessions" in detail_html

    # Non-owner tries to edit listing - should receive 403 Forbidden
    with app.app_context():
        other_user = user_factory(email="other@example.com")
    
    client.get("/auth/logout", follow_redirects=True)
    login("other@example.com")
    res = client.get(f"/listings/{listing.id}/edit")
    assert res.status_code == 403

    res = client.post(f"/listings/{listing.id}/edit", data={
        "title": "Malicious Title Edit",
        "description": "Malicious description edit.",
        "exchange_type": "credit",
        "skill_id": str(ps1.id),
        "category_id": str(tech_cat.id),
        "min_credits": "10",
        "location_text": "Kathmandu",
        "contact_method": "In-app messaging",
        "availability_labels": "Weekends only"
    })
    assert res.status_code == 403

    # Owner edits listing
    client.get("/auth/logout", follow_redirects=True)
    login("alice@example.com")
    res = client.get(f"/listings/{listing.id}/edit")
    assert res.status_code == 200
    edit_form_html = res.data.decode("utf-8")
    assert "Learn Python step by step" in edit_form_html

    res = client.post(f"/listings/{listing.id}/edit", data={
        "title": "Learn Python step by step - Updated",
        "description": "Updated description with more than ten characters.",
        "exchange_type": "teach",  # change exchange type
        "skill_id": str(ps1.id),
        "category_id": str(tech_cat.id),
        "min_credits": "0",
        "location_text": "Remote",
        "contact_method": "Email",
        "availability_labels": "Weekdays 8pm"
    }, follow_redirects=True)

    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Listing updated successfully and is pending admin review." in html
    assert "Learn Python step by step - Updated" in html

    # Verify updated values in db
    with app.app_context():
        listing = Skill.find_by_id(listing.id)
        assert listing.title == "Learn Python step by step - Updated"
        assert listing.description == "Updated description with more than ten characters."
        assert listing.exchange_type == "teach"
        assert listing.credit_cost == 0
        assert listing.location_text == "Remote"
        assert listing.contact_method == "Email"
        assert listing.status == "pending"

    # Non-owner tries to delete listing - 403 Forbidden
    client.get("/auth/logout", follow_redirects=True)
    login("other@example.com")
    res = client.post(f"/listings/{listing.id}/delete")
    assert res.status_code == 403

    # Owner deletes listing
    client.get("/auth/logout", follow_redirects=True)
    login("alice@example.com")
    res = client.post(f"/listings/{listing.id}/delete", follow_redirects=True)
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Listing deleted successfully." in html
    assert "Learn Python step by step - Updated" not in html

    # Verify deleted from db
    with app.app_context():
        assert Skill.find_by_id(listing.id) is None


def test_marketplace_search_and_api(app, client, login, user_factory, seed_categories):
    with app.app_context():
        user = user_factory(email="alice@example.com")
        ps1 = ProfileSkill.create(user.id, "Python coding", SkillType.OFFERED)
        ps2 = ProfileSkill.create(user.id, "Piano tutorial", SkillType.OFFERED)
        tech_cat = seed_categories["Tech"]
        music_cat = seed_categories["Music"]

        # Create two listings.
        # Direct SQL write to set status to 'approved' so they appear in public search.
        from app.database import Database
        db = Database()
        db.execute(
            """
            INSERT INTO skills (user_id, category_id, skill_id, title, description, exchange_type, credit_cost, availability, location_text, contact_method, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'approved')
            """,
            (user.id, tech_cat.id, ps1.id, "Python Basics Masterclass", "Let us learn Python code from scratch.", "credit", 10, "Daily", "Kathmandu", "Platform",)
        )
        db.execute(
            """
            INSERT INTO skills (user_id, category_id, skill_id, title, description, exchange_type, credit_cost, availability, location_text, contact_method, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'approved')
            """,
            (user.id, music_cat.id, ps2.id, "Piano Lessons for Kids", "Teach kids how to play beautiful melodies on piano.", "teach", 0, "Sunday", "Lalitpur", "Email",)
        )

    # 1. Search for keyword "Python" in marketplace
    res = client.get("/listings/?q=Python")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Python Basics Masterclass" in html
    assert "Piano Lessons for Kids" not in html

    # 2. Search for Category "Music" in marketplace
    res = client.get(f"/listings/?category={music_cat.id}")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Piano Lessons for Kids" in html
    assert "Python Basics Masterclass" not in html

    # 3. API Search endpoint returns correct partial HTML structure
    res = client.get(f"/listings/api/search?q=Piano")
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["count"] == 1
    assert "Piano Lessons for Kids" in json_data["html"]
    assert "Python Basics" not in json_data["html"]
