from app.models import User, ProfileSkill, Profile
from app.database import Database
from app.models.notification import Notification

def test_us11_01_mutual_match(app, user_factory):
    with app.app_context():
        user_a = user_factory(email="a@example.com", full_name="User A")
        user_b = user_factory(email="b@example.com", full_name="User B")

        ProfileSkill.create(user_a.id, "Guitar", "offered")
        ProfileSkill.create(user_a.id, "Python", "wanted")

        ProfileSkill.create(user_b.id, "Python", "offered")
        ProfileSkill.create(user_b.id, "Guitar", "wanted")

        matches_a = Profile.get_mutual_matches(user_a.id)
        assert len(matches_a) == 1
        assert matches_a[0]["matched_user_id"] == user_b.id

        matches_b = Profile.get_mutual_matches(user_b.id)
        assert len(matches_b) == 1
        assert matches_b[0]["matched_user_id"] == user_a.id

def test_us11_02_no_overlapping_skills(app, user_factory):
    with app.app_context():
        user_a = user_factory(email="a@example.com", full_name="User A")
        user_b = user_factory(email="b@example.com", full_name="User B")

        ProfileSkill.create(user_a.id, "Guitar", "offered")
        ProfileSkill.create(user_a.id, "Python", "wanted")

        ProfileSkill.create(user_b.id, "Cooking", "offered")
        ProfileSkill.create(user_b.id, "Math", "wanted")

        matches_a = Profile.get_mutual_matches(user_a.id)
        assert len(matches_a) == 0

def test_us11_03_banned_user_hidden(app, user_factory):
    with app.app_context():
        user_a = user_factory(email="a@example.com", full_name="User A")
        user_b = user_factory(email="b@example.com", full_name="User B")

        ProfileSkill.create(user_a.id, "Guitar", "offered")
        ProfileSkill.create(user_a.id, "Python", "wanted")

        ProfileSkill.create(user_b.id, "Python", "offered")
        ProfileSkill.create(user_b.id, "Guitar", "wanted")

        db = Database()
        try:
            db.execute("UPDATE users SET status = 'banned' WHERE id = %s", (user_b.id,))
        finally:
            db.close()

        matches_a = Profile.get_mutual_matches(user_a.id)
        assert len(matches_a) == 0

def test_us11_04_match_score(app, user_factory):
    with app.app_context():
        user_a = user_factory(email="a@example.com", full_name="User A")
        user_b = user_factory(email="b@example.com", full_name="User B")
        user_c = user_factory(email="c@example.com", full_name="User C")

        ProfileSkill.create(user_a.id, "Guitar", "offered")
        ProfileSkill.create(user_a.id, "Piano", "offered")
        ProfileSkill.create(user_a.id, "Python", "wanted")

        ProfileSkill.create(user_b.id, "Python", "offered")
        ProfileSkill.create(user_b.id, "Guitar", "wanted")
        ProfileSkill.create(user_b.id, "Piano", "wanted")

        ProfileSkill.create(user_c.id, "Python", "offered")
        ProfileSkill.create(user_c.id, "Guitar", "wanted")

        matches_a = Profile.get_mutual_matches(user_a.id)
        assert len(matches_a) == 2
        assert matches_a[0]["matched_user_id"] == user_b.id
        assert matches_a[0]["match_score"] == 3
        assert matches_a[1]["matched_user_id"] == user_c.id
        assert matches_a[1]["match_score"] == 2

def test_us11_05_notification_created(app, client, user_factory, login):
    with app.app_context():
        user_a = user_factory(email="a@example.com", full_name="User A")
        user_b = user_factory(email="b@example.com", full_name="User B")

        ProfileSkill.create(user_b.id, "Python", "offered")
        ProfileSkill.create(user_b.id, "Guitar", "wanted")

    login("a@example.com", "Password123!")

    response = client.post("/profile/edit", data={
        "full_name": "User A",
        "location": "Kathmandu",
        "bio": "Test bio",
        "offered_skills": ["Guitar"],
        "wanted_skills": ["Python"]
    }, follow_redirects=True)

    assert response.status_code == 200

    with app.app_context():
        from app.repositories import NotificationRepository
        notifs_a = NotificationRepository().get_unread_notifications(user_a.id)
        notifs_b = NotificationRepository().get_unread_notifications(user_b.id)

        assert any(n.type == "new_match" for n in notifs_a)
        assert any(n.type == "new_match" for n in notifs_b)

def test_us11_06_unauthenticated_redirect(client):
    response = client.get("/matches/", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
