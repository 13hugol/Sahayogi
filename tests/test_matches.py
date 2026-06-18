from __future__ import annotations

from app.dto import MutualSkillMatch
from app.services import MatchService


def test_match_service_returns_no_matches_when_user_lacks_skills(app):
    with app.app_context():
        from app.models import User
        from app.repositories import (
            NotificationRepository,
            ProfileRepository,
            ProfileSkillRepository,
            RoleRepository,
            UserRepository,
        )

        user = User.all()[0] if User.all() else None
        if not user:
            return  # nothing to test without seed users
        service = MatchService(
            user_repository=UserRepository(
                role_repository=RoleRepository(),
                profile_repository=ProfileRepository(),
            ),
            profile_skill_repository=ProfileSkillRepository(),
            notification_repository=NotificationRepository(),
        )
        # If no offered or wanted skills, expect empty list (the user fixture is
        # created without profile skills by default)
        matches = service.mutual_matches_for_user(user, notify=False)
        assert matches == []


def test_match_service_finds_mutual_overlap(app, user_factory):
    with app.app_context():
        from app.models.profile import ProfileSkill
        from app.repositories import (
            NotificationRepository,
            ProfileRepository,
            ProfileSkillRepository,
            RoleRepository,
            UserRepository,
        )
        from app.services import MatchService

        user_a = user_factory(email="matcha@example.com", verified=True)
        user_b = user_factory(email="matchb@example.com", verified=True)
        user_c = user_factory(email="matchc@example.com", verified=True)

        # user_a offers Python, wants Guitar
        ProfileSkill.create(user_a.id, "Python", "offered")
        ProfileSkill.create(user_a.id, "Guitar", "wanted")
        # user_b offers Guitar, wants Python — mutual with user_a
        ProfileSkill.create(user_b.id, "Guitar", "offered")
        ProfileSkill.create(user_b.id, "Python", "wanted")
        # user_c offers Cooking only — no overlap with user_a
        ProfileSkill.create(user_c.id, "Cooking", "offered")
        ProfileSkill.create(user_c.id, "Python", "wanted")

        service = MatchService(
            user_repository=UserRepository(
                role_repository=RoleRepository(),
                profile_repository=ProfileRepository(),
            ),
            profile_skill_repository=ProfileSkillRepository(),
            notification_repository=NotificationRepository(),
        )
        matches = service.mutual_matches_for_user(user_a, notify=False)
        assert len(matches) == 1
        match = matches[0]
        assert match.user.id == user_b.id
        assert "Python" in match.my_offers_they_want
        assert "Guitar" in match.their_offers_i_want
        assert match.relevance_score > 0
        assert match.is_new is False


def test_match_service_creates_unique_notifications(app, user_factory):
    with app.app_context():
        from app.models.profile import ProfileSkill
        from app.repositories import (
            NotificationRepository,
            ProfileRepository,
            ProfileSkillRepository,
            RoleRepository,
            UserRepository,
        )
        from app.services import MatchService

        user_a = user_factory(email="notifmatcha@example.com", verified=True)
        user_b = user_factory(email="notifmatchb@example.com", verified=True)

        ProfileSkill.create(user_a.id, "Cooking", "offered")
        ProfileSkill.create(user_a.id, "Spanish", "wanted")
        ProfileSkill.create(user_b.id, "Spanish", "offered")
        ProfileSkill.create(user_b.id, "Cooking", "wanted")

        notif_repo = NotificationRepository()
        service = MatchService(
            user_repository=UserRepository(
                role_repository=RoleRepository(),
                profile_repository=ProfileRepository(),
            ),
            profile_skill_repository=ProfileSkillRepository(),
            notification_repository=notif_repo,
        )
        first = service.mutual_matches_for_user(user_a, notify=True)
        assert len(first) == 1
        assert first[0].is_new is True

        second = service.mutual_matches_for_user(user_a, notify=True)
        assert len(second) == 1
        assert second[0].is_new is False  # already notified


def test_match_dto_summary():
    match = MutualSkillMatch(
        user=None,  # type: ignore[arg-type]
        my_offers_they_want=("Python", "Flask"),
        their_offers_i_want=("Spanish",),
        relevance_score=200,
    )
    assert "Python" in match.summary
    assert "Spanish" in match.summary
    assert match.overlap_count == 3


def test_matches_route_requires_login(app, client):
    response = client.get("/matches/")
    assert response.status_code == 302
    assert "login" in response.headers["Location"]


def test_matches_route_renders_for_logged_in_user(app, client, login, user_factory):
    with app.app_context():
        user_factory(email="matchesviewer@example.com", verified=True)
    login("matchesviewer@example.com")
    response = client.get("/matches/")
    assert response.status_code == 200
    content = response.data.decode("utf-8")
    assert "Skill matches" in content
