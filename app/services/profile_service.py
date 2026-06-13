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

    def get_review_history(self, user_id: int, *, page: int = 1, per_page: int = 10):
        user = self._user_repository.find_by_id(user_id)
        if not user or not user.profile:
            raise ProfileNotFoundError(user_id)
        reviews = self._review_repository.for_user(user.id, page=page, per_page=per_page)
        total = self._review_repository.count_for_user(user.id)
        return user, reviews, total

    def get_top_rated_profiles(self, limit: int = 12):
        return self._profile_repository.top_rated(limit)

