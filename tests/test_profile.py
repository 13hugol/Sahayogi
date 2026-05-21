from __future__ import annotations

from app.database import Database
from app.models import ProfileCertificate, ProfileReview, ProfileSkill


def test_guest_profile_page_shows_profile_story_details(app, client, user_factory):
    with app.app_context():
        member = user_factory(full_name="Maya Gurung", email="maya@example.com")
        _update_profile_summary(member.id)
        offered = ProfileSkill.create(member.id, "Python mentoring", "offered")
        ProfileSkill.create(member.id, "Guitar basics", "wanted")
        ProfileCertificate.create(
            user_id=member.id,
            profile_skill_id=offered.id,
            skill_name=offered.skill_name,
            status="approved",
        )
        ProfileReview.create(
            reviewee_user_id=member.id,
            reviewer_name="Priya Reviewer",
            rating=5,
            comment="Patient and clear in every session.",
        )
        member_id = member.id

    response = client.get(f"/users/{member_id}")

    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Maya Gurung" in html
    assert "Kathmandu" in html
    assert "Builds calm Python lessons for beginners." in html
    assert "Python mentoring" in html
    assert "Guitar basics" in html
    assert "Verified certificate" in html
    assert "Reputation: 4.8 / 5" in html
    assert "Completed exchanges: 7" in html
    assert "Priya Reviewer" in html
    assert "Patient and clear in every session." in html
    assert "Join Sahayogi" in html


def test_logged_in_user_can_view_another_member_profile(app, client, login, user_factory):
    with app.app_context():
        viewer = user_factory(full_name="Viewer User", email="viewer@example.com")
        member = user_factory(full_name="Profile Owner", email="owner@example.com")
        ProfileSkill.create(member.id, "Kitchen basics", "offered")
        member_id = member.id

    login(viewer.email)
    response = client.get(f"/users/{member_id}")

    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Profile Owner" in html
    assert "Kitchen basics" in html
    assert "Join Sahayogi" not in html


def test_profile_me_shows_current_user_profile(app, client, login, user_factory):
    with app.app_context():
        member = user_factory(full_name="Current Member", email="current@example.com")
        ProfileSkill.create(member.id, "Language practice", "wanted")

    login("current@example.com")
    response = client.get("/profile/me")

    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Current Member" in html
    assert "Language practice" in html


def _update_profile_summary(user_id: int) -> None:
    db = Database()
    try:
        db.execute(
            """
            UPDATE profiles
            SET headline = %s,
                bio = %s,
                reputation_score = %s,
                review_count = %s,
                completed_exchange_count = %s
            WHERE user_id = %s
            """,
            (
                "Peer tutor and patient collaborator",
                "Builds calm Python lessons for beginners.",
                4.8,
                4,
                7,
                user_id,
            ),
        )
    finally:
        db.close()
