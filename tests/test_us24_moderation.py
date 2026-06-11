from __future__ import annotations

import pytest
from app.models.skill import Skill, Category
from app.models.profile import ProfileSkill
from app.models.notification import Notification
from app.repositories import SkillRepository, CategoryRepository
from app.enums import SkillType
from app.database import Database

@pytest.fixture()
def seed_data(app, user_factory):
    with app.app_context():
        # Create categories
        cat_repo = CategoryRepository()
        tech = cat_repo.ensure("Tech", "Tech skills")
        music = cat_repo.ensure("Music", "Music skills")

        # Create admin and regular users
        admin = user_factory(email="admin@example.com", role_name="admin")
        alice = user_factory(email="alice@example.com") # username: alice
        bob = user_factory(email="bob@example.com")     # username: bob

        # Create profile skills
        ps_alice = ProfileSkill.create(alice.id, "Python coding", SkillType.OFFERED)
        ps_bob_g = ProfileSkill.create(bob.id, "Guitar tutoring", SkillType.OFFERED)
        ps_bob_p = ProfileSkill.create(bob.id, "Programming", SkillType.OFFERED)

        db = Database()
        # Seed pending listings with specific creation times
        # 1. Alice's Tech Skill (pending)
        db.execute(
            """
            INSERT INTO skills (user_id, category_id, skill_id, title, description, exchange_type, credit_cost, availability, location_text, contact_method, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', '2026-05-25 10:00:00')
            """,
            (alice.id, tech.id, ps_alice.id, "Alice Tech Skill", "Python development.", "credit", 10, "Daily", "Kathmandu", "Platform")
        )
        
        # 2. Bob's Music Skill (pending)
        db.execute(
            """
            INSERT INTO skills (user_id, category_id, skill_id, title, description, exchange_type, credit_cost, availability, location_text, contact_method, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', '2026-05-25 09:00:00')
            """,
            (bob.id, music.id, ps_bob_g.id, "Bob Music Skill", "Guitar lessons.", "teach", 0, "Sunday", "Lalitpur", "Email")
        )

        # 3. Bob's Tech Skill (pending)
        db.execute(
            """
            INSERT INTO skills (user_id, category_id, skill_id, title, description, exchange_type, credit_cost, availability, location_text, contact_method, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', '2026-05-25 11:00:00')
            """,
            (bob.id, tech.id, ps_bob_p.id, "Bob Tech Skill", "Python & SQL.", "credit", 15, "Monday", "Pokhara", "In-app")
        )

        # 4. Already approved listing (should not show in pending queue)
        ps_alice_approved = ProfileSkill.create(alice.id, "Web design", SkillType.OFFERED)
        db.execute(
            """
            INSERT INTO skills (user_id, category_id, skill_id, title, description, exchange_type, credit_cost, availability, location_text, contact_method, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'approved', '2026-05-25 08:00:00')
            """,
            (alice.id, tech.id, ps_alice_approved.id, "Alice Web Design", "HTML/CSS masterclass", "credit", 20, "Daily", "Kathmandu", "Platform")
        )

        # Get the ID of Bob's Tech Skill and Bob's Music Skill for direct tests
        rows = db.fetch_all("SELECT id, title FROM skills WHERE status = 'pending' ORDER BY id")
        pending_ids = {row["title"]: row["id"] for row in rows}

        return {
            "admin": admin,
            "alice": alice,
            "bob": bob,
            "tech_cat": tech,
            "music_cat": music,
            "pending_ids": pending_ids
        }


def test_admin_listings_queue_no_filter(app, client, login, seed_data):
    login("admin@example.com")
    res = client.get("/admin/listings")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    # All three pending skills should be visible
    assert "Alice Tech Skill" in html
    assert "Bob Music Skill" in html
    assert "Bob Tech Skill" in html
    # The approved listing should not be in the pending queue
    assert "Alice Web Design" not in html


def test_admin_listings_queue_filter_category(app, client, login, seed_data):
    login("admin@example.com")
    tech_id = seed_data["tech_cat"].id
    music_id = seed_data["music_cat"].id

    # Filter Tech
    res = client.get(f"/admin/listings?category_id={tech_id}")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Alice Tech Skill" in html
    assert "Bob Tech Skill" in html
    assert "Bob Music Skill" not in html

    # Filter Music
    res = client.get(f"/admin/listings?category_id={music_id}")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Bob Music Skill" in html
    assert "Alice Tech Skill" not in html
    assert "Bob Tech Skill" not in html


def test_admin_listings_queue_filter_username(app, client, login, seed_data):
    login("admin@example.com")

    # Filter Alice
    res = client.get("/admin/listings?username=alice")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Alice Tech Skill" in html
    assert "Bob Tech Skill" not in html
    assert "Bob Music Skill" not in html

    # Filter Bob
    res = client.get("/admin/listings?username=bob")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Bob Tech Skill" in html
    assert "Bob Music Skill" in html
    assert "Alice Tech Skill" not in html


def test_admin_listings_queue_filter_combined(app, client, login, seed_data):
    login("admin@example.com")
    tech_id = seed_data["tech_cat"].id

    res = client.get(f"/admin/listings?category_id={tech_id}&username=bob")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Bob Tech Skill" in html
    assert "Alice Tech Skill" not in html
    assert "Bob Music Skill" not in html


def test_admin_listings_queue_sorting(app, client, login, seed_data):
    login("admin@example.com")

    # Default/descending order (newest first):
    # Bob Tech Skill (11:00) -> Alice Tech Skill (10:00) -> Bob Music Skill (09:00)
    res = client.get("/admin/listings?sort_order=desc")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    idx_bob_t = html.find("Bob Tech Skill")
    idx_alice_t = html.find("Alice Tech Skill")
    idx_bob_m = html.find("Bob Music Skill")
    assert idx_bob_t < idx_alice_t < idx_bob_m

    # Ascending order (oldest first):
    # Bob Music Skill (09:00) -> Alice Tech Skill (10:00) -> Bob Tech Skill (11:00)
    res = client.get("/admin/listings?sort_order=asc")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    idx_bob_t = html.find("Bob Tech Skill")
    idx_alice_t = html.find("Alice Tech Skill")
    idx_bob_m = html.find("Bob Music Skill")
    assert idx_bob_m < idx_alice_t < idx_bob_t


def test_admin_listing_approval(app, client, login, seed_data):
    login("admin@example.com")
    listing_id = seed_data["pending_ids"]["Alice Tech Skill"]

    # Approve listing
    res = client.post(f"/admin/listings/{listing_id}/approve", follow_redirects=True)
    assert res.status_code == 200
    
    with app.app_context():
        # Verify status is updated to approved
        listing = SkillRepository().find_by_id(listing_id)
        assert listing.status == "approved"
        assert listing.rejection_reason is None


def test_admin_listing_rejection_success(app, client, login, seed_data):
    login("admin@example.com")
    listing_id = seed_data["pending_ids"]["Bob Music Skill"]
    bob_id = seed_data["bob"].id

    # Reject listing with reason
    res = client.post(
        f"/admin/listings/{listing_id}/reject",
        data={"reason": "Incomplete availability description"},
        follow_redirects=True
    )
    assert res.status_code == 200

    with app.app_context():
        # Verify status is updated to rejected
        listing = SkillRepository().find_by_id(listing_id)
        assert listing.status == "rejected"
        assert listing.rejection_reason == "Incomplete availability description"

        # Verify a notification is created for Bob
        unread_count = Notification.get_unread_count(bob_id)
        assert unread_count == 1
        
        notifications = Notification.get_unread_notifications(bob_id)
        assert len(notifications) == 1
        assert "rejected" in notifications[0].message
        assert "Incomplete availability description" in notifications[0].message


def test_admin_listing_rejection_missing_reason(app, client, login, seed_data):
    login("admin@example.com")
    listing_id = seed_data["pending_ids"]["Bob Tech Skill"]
    bob_id = seed_data["bob"].id

    # Reject listing with empty reason
    res = client.post(
        f"/admin/listings/{listing_id}/reject",
        data={"reason": "  "},
        follow_redirects=True
    )
    assert res.status_code == 200

    with app.app_context():
        # Verify listing status is still pending
        listing = SkillRepository().find_by_id(listing_id)
        assert listing.status == "pending"
        
        # Verify no notification created
        unread_count = Notification.get_unread_count(bob_id)
        assert unread_count == 0


def test_non_admin_access_denied(app, client, login, seed_data):
    # Log in as Alice (regular user)
    login("alice@example.com")
    listing_id = seed_data["pending_ids"]["Bob Music Skill"]

    # Try accessing listings queue
    res = client.get("/admin/listings")
    assert res.status_code == 403

    # Try approving
    res = client.post(f"/admin/listings/{listing_id}/approve")
    assert res.status_code == 403

    # Try rejecting
    res = client.post(f"/admin/listings/{listing_id}/reject", data={"reason": "reason"})
    assert res.status_code == 403
