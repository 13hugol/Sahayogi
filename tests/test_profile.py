from __future__ import annotations

import base64
import io
from pathlib import Path

from app.database import Database
from app.models import ProfileCertificate, ProfileReview, ProfileSkill, User


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


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
        # Four earlier reviews so the recalculated average lands on 4.8 (24 / 5).
        for rating in (5, 5, 5, 4):
            ProfileReview.create(
                reviewee_user_id=member.id,
                reviewer_name="Past Learner",
                rating=rating,
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
    assert "Reputation:" in html
    assert "4.8 / 5" in html
    assert "New Member" not in html
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


def test_edit_profile_form_prefills_existing_data(app, client, login, user_factory):
    with app.app_context():
        member = user_factory(full_name="Maya Gurung", email="maya-edit@example.com")
        _update_profile_summary(member.id)
        ProfileSkill.create(member.id, "Python mentoring", "offered")
        ProfileSkill.create(member.id, "Guitar basics", "wanted")

    login("maya-edit@example.com")
    response = client.get("/profile/edit")

    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert 'name="full_name"' in html
    assert 'value="Maya Gurung"' in html
    assert 'name="location"' in html
    assert 'value="Kathmandu"' in html
    assert "Builds calm Python lessons for beginners." in html
    assert "Python mentoring" in html
    assert "Guitar basics" in html
    assert "JPG or PNG under 5MB" in html


def test_edit_profile_updates_profile_and_syncs_skills(app, client, login, user_factory):
    with app.app_context():
        member = user_factory(full_name="Profile Editor", email="editor@example.com")
        kept_skill = ProfileSkill.create(member.id, "Python mentoring", "offered")
        ProfileSkill.create(member.id, "Excel cleanup", "offered")
        ProfileSkill.create(member.id, "Guitar basics", "wanted")
        ProfileCertificate.create(
            user_id=member.id,
            profile_skill_id=kept_skill.id,
            skill_name=kept_skill.skill_name,
            status="approved",
        )
        member_id = member.id
        kept_skill_id = kept_skill.id

    login("editor@example.com")
    response = client.post(
        "/profile/edit",
        data={
            "full_name": "Profile Editor Updated",
            "location": "Pokhara",
            "bio": "Updated bio for skill exchange partners.",
            "offered_skills": ["Python mentoring", "Public speaking"],
            "wanted_skills": ["Guitar basics", "Watercolor basics"],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Profile updated successfully." in html

    with app.app_context():
        updated_user = User.find_by_id(member_id)
        offered_skills = ProfileSkill.find_for_user(member_id, "offered")
        wanted_skills = ProfileSkill.find_for_user(member_id, "wanted")
        certificates = ProfileCertificate.approved_for_user(member_id)

    assert updated_user.full_name == "Profile Editor Updated"
    assert updated_user.profile.location == "Pokhara"
    assert updated_user.profile.bio == "Updated bio for skill exchange partners."
    assert [skill.skill_name for skill in offered_skills] == ["Python mentoring", "Public speaking"]
    assert [skill.skill_name for skill in wanted_skills] == ["Guitar basics", "Watercolor basics"]
    assert any(skill.id == kept_skill_id for skill in offered_skills)
    assert certificates[0].profile_skill_id == kept_skill_id


def test_edit_profile_rejects_invalid_avatar(app, client, login, user_factory):
    with app.app_context():
        member = user_factory(email="bad-avatar@example.com")
        member_id = member.id

    login("bad-avatar@example.com")
    response = client.post(
        "/profile/edit",
        data={
            "full_name": "Test Member",
            "location": "Kathmandu",
            "bio": "",
            "offered_skills": [],
            "wanted_skills": [],
            "avatar": (io.BytesIO(b"not an image"), "avatar.gif"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Avatar must be a JPG or PNG file." in html

    with app.app_context():
        user = User.find_by_id(member_id)
    assert user.profile.avatar_path is None


def test_edit_profile_saves_valid_png_avatar(app, client, login, user_factory, tmp_path):
    app.config["UPLOAD_FOLDER"] = tmp_path
    with app.app_context():
        member = user_factory(email="avatar@example.com")
        member_id = member.id

    login("avatar@example.com")
    response = client.post(
        "/profile/edit",
        data={
            "full_name": "Avatar Member",
            "location": "Bhaktapur",
            "bio": "Avatar upload test.",
            "offered_skills": ["Python mentoring"],
            "wanted_skills": ["Music theory"],
            "avatar": (io.BytesIO(PNG_BYTES), "avatar.png"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Profile updated successfully." in response.data.decode("utf-8")

    with app.app_context():
        user = User.find_by_id(member_id)
        avatar_path = user.profile.avatar_path
        saved_avatar = Path(app.config["UPLOAD_FOLDER"]) / avatar_path

    assert avatar_path.startswith("avatars/user-")
    assert saved_avatar.exists()


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
