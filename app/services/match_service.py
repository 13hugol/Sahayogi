from __future__ import annotations

from app.dto import MutualSkillMatch
from app.enums import SkillType
from app.models import User
from app.repositories import (
    NotificationRepository,
    ProfileSkillRepository,
    UserRepository,
)


class MatchService:
    def __init__(
        self,
        user_repository: UserRepository,
        profile_skill_repository: ProfileSkillRepository,
        notification_repository: NotificationRepository | None = None,
    ):
        self._user_repository = user_repository
        self._profile_skill_repository = profile_skill_repository
        self._notification_repository = notification_repository or NotificationRepository()

    def mutual_matches_for_user(
        self,
        user: User,
        *,
        notify: bool = False,
    ) -> list[MutualSkillMatch]:
        my_offered = self._skill_lookup(user.id, SkillType.OFFERED)
        my_wanted = self._skill_lookup(user.id, SkillType.WANTED)
        if not my_offered or not my_wanted:
            return []

        candidates = self._user_repository.all()
        matches: list[MutualSkillMatch] = []
        for candidate in candidates:
            if candidate.id == user.id:
                continue
            if getattr(candidate, "status", "active") not in {"active", None}:
                continue

            candidate_offered = self._skill_lookup(candidate.id, SkillType.OFFERED)
            candidate_wanted = self._skill_lookup(candidate.id, SkillType.WANTED)
            my_offers_they_want = self._overlap(my_offered, candidate_wanted)
            their_offers_i_want = self._overlap(my_wanted, candidate_offered)
            if not my_offers_they_want or not their_offers_i_want:
                continue

            relevance = self._relevance_score(candidate, my_offers_they_want, their_offers_i_want)
            is_new = False
            if notify:
                is_new = self._notify(user, candidate, my_offers_they_want, their_offers_i_want)

            matches.append(
                MutualSkillMatch(
                    user=candidate,
                    my_offers_they_want=tuple(my_offers_they_want),
                    their_offers_i_want=tuple(their_offers_i_want),
                    relevance_score=relevance,
                    is_new=is_new,
                )
            )

        return sorted(
            matches,
            key=lambda m: (
                m.relevance_score,
                m.user.profile.reputation_score if m.user.profile else 0,
                m.user.full_name.lower(),
            ),
            reverse=True,
        )

    def _skill_lookup(self, user_id: int, skill_type: SkillType) -> dict[str, str]:
        skills = self._profile_skill_repository.find_for_user(user_id, skill_type)
        return {self._normalize(skill.skill_name): skill.skill_name for skill in skills}

    @staticmethod
    def _overlap(first: dict[str, str], second: dict[str, str]) -> list[str]:
        return sorted(first[key] for key in first.keys() & second.keys())

    @staticmethod
    def _normalize(skill_name: str) -> str:
        return " ".join(skill_name.split()).casefold()

    @staticmethod
    def _relevance_score(
        user: User,
        my_offers_they_want: list[str],
        their_offers_i_want: list[str],
    ) -> int:
        overlap_score = (len(my_offers_they_want) + len(their_offers_i_want)) * 50
        reputation = user.profile.reputation_score if user.profile else 0
        reputation_score = int(round(float(reputation or 0) * 10))
        return overlap_score + reputation_score

    def _notify(
        self,
        user: User,
        candidate: User,
        my_offers_they_want: list[str],
        their_offers_i_want: list[str],
    ) -> bool:
        body = self._notification_message(candidate, my_offers_they_want, their_offers_i_want)
        if self._notification_repository.message_exists(user.id, body):
            return False
        self._notification_repository.create(
            user_id=user.id,
            event_type="new_match",
            title="New mutual match",
            body=body,
            target_url=f"/matches#match-{candidate.id}",
        )
        return True

    @staticmethod
    def _notification_message(
        user: User,
        my_offers_they_want: list[str],
        their_offers_i_want: list[str],
    ) -> str:
        return (
            f"New mutual match with {user.full_name}: "
            f"you can offer {', '.join(my_offers_they_want)} and learn {', '.join(their_offers_i_want)}."
        )
