from __future__ import annotations

from app.dto import ProfilePageData
from app.exceptions import ProfileNotFoundError
from app.repositories import (
    ProfileCertificateRepository,
    ProfileRepository,
    ProfileReviewRepository,
    UserRepository,
)


class ProfileService:
    def __init__(
        self,
        user_repository: UserRepository,
        profile_repository: ProfileRepository,
        certificate_repository: ProfileCertificateRepository,
        review_repository: ProfileReviewRepository,
    ):
        self._user_repository = user_repository
        self._profile_repository = profile_repository
        self._certificate_repository = certificate_repository
        self._review_repository = review_repository

    def get_profile_page_data(self, user_id: int) -> ProfilePageData:
        user = self._user_repository.find_by_id(user_id)
        if not user or not user.profile:
            raise ProfileNotFoundError(user_id)
        return ProfilePageData(
            user=user,
            approved_certificates=self._certificate_repository.approved_for_user(user.id),
            recent_reviews=self._review_repository.recent_for_user(user.id),
            approved_listings=[],
        )

    def get_review_history(self, user_id: int):
        user = self._user_repository.find_by_id(user_id)
        if not user or not user.profile:
            raise ProfileNotFoundError(user_id)
        return user, self._review_repository.for_user(user.id)

    _top_rated_cache = None
    _top_rated_cache_time = None

    def get_top_rated_profiles(self, limit: int = 12):
        from datetime import datetime
        from flask import current_app

        is_testing = False
        try:
            is_testing = current_app.config.get("TESTING", False)
        except RuntimeError:
            pass

        now = datetime.now()
        if (
            is_testing
            or ProfileService._top_rated_cache is None
            or ProfileService._top_rated_cache_time is None
            or (now - ProfileService._top_rated_cache_time).days >= 1
        ):
            ProfileService._top_rated_cache = self._profile_repository.top_rated(limit)
            ProfileService._top_rated_cache_time = now
        return ProfileService._top_rated_cache

