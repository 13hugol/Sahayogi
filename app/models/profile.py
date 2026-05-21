from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace

from app.enums import CertificateStatus, SkillType

from .base_model import BaseModel


@dataclass
class ProfileSkill(BaseModel):
    id: int
    user_id: int
    skill_name: str
    skill_type: str
    sort_order: int = 0
    has_verified_certificate: bool = False

    @property
    def skill(self):
        return SimpleNamespace(id=self.id, name=self.skill_name)

    @classmethod
    def from_row(cls, row: dict | None) -> "ProfileSkill | None":
        if not row:
            return None
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            skill_name=row["skill_name"],
            skill_type=row["skill_type"],
            sort_order=int(row.get("sort_order") or 0),
            has_verified_certificate=bool(row.get("has_verified_certificate")),
        )

    @classmethod
    def find_for_user(cls, user_id: int, skill_type: str | SkillType) -> list["ProfileSkill"]:
        from app.repositories import ProfileSkillRepository

        return ProfileSkillRepository().find_for_user(user_id, skill_type)

    @classmethod
    def create(
        cls,
        user_id: int,
        skill_name: str,
        skill_type: str | SkillType,
        sort_order: int = 0,
    ) -> "ProfileSkill":
        from app.repositories import ProfileSkillRepository

        return ProfileSkillRepository().create(user_id, skill_name, skill_type, sort_order)


@dataclass
class ProfileCertificate(BaseModel):
    id: int
    user_id: int
    profile_skill_id: int | None
    skill_name: str
    status: str
    file_path: str | None = None
    review_notes: str | None = None
    created_at: datetime | None = None

    @property
    def skill(self):
        return SimpleNamespace(id=self.profile_skill_id, name=self.skill_name)

    @classmethod
    def from_row(cls, row: dict | None) -> "ProfileCertificate | None":
        if not row:
            return None
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            profile_skill_id=row.get("profile_skill_id"),
            skill_name=row["skill_name"],
            status=row["status"],
            file_path=row.get("file_path"),
            review_notes=row.get("review_notes"),
            created_at=row.get("created_at"),
        )

    @classmethod
    def approved_for_user(cls, user_id: int) -> list["ProfileCertificate"]:
        from app.repositories import ProfileCertificateRepository

        return ProfileCertificateRepository().approved_for_user(user_id)

    @classmethod
    def create(
        cls,
        *,
        user_id: int,
        skill_name: str,
        profile_skill_id: int | None = None,
        status: str = CertificateStatus.PENDING.value,
        file_path: str | None = None,
        review_notes: str | None = None,
    ) -> "ProfileCertificate":
        from app.repositories import ProfileCertificateRepository

        return ProfileCertificateRepository().create(
            user_id=user_id,
            skill_name=skill_name,
            profile_skill_id=profile_skill_id,
            status=status,
            file_path=file_path,
            review_notes=review_notes,
        )


@dataclass
class ProfileReview(BaseModel):
    id: int
    reviewee_user_id: int
    reviewer_id: int | None
    reviewer_name: str
    rating: int
    comment: str | None = None
    created_at: datetime | None = None

    @property
    def reviewer(self):
        return SimpleNamespace(id=self.reviewer_id, full_name=self.reviewer_name)

    @classmethod
    def from_row(cls, row: dict | None) -> "ProfileReview | None":
        if not row:
            return None
        return cls(
            id=row["id"],
            reviewee_user_id=row["reviewee_user_id"],
            reviewer_id=row.get("reviewer_id"),
            reviewer_name=row["reviewer_name"],
            rating=int(row.get("rating") or 0),
            comment=row.get("comment"),
            created_at=row.get("created_at"),
        )

    @classmethod
    def recent_for_user(cls, user_id: int, limit: int = 3) -> list["ProfileReview"]:
        from app.repositories import ProfileReviewRepository

        return ProfileReviewRepository().recent_for_user(user_id, limit)

    @classmethod
    def for_user(cls, user_id: int) -> list["ProfileReview"]:
        from app.repositories import ProfileReviewRepository

        return ProfileReviewRepository().for_user(user_id)

    @classmethod
    def create(
        cls,
        *,
        reviewee_user_id: int,
        reviewer_name: str,
        rating: int,
        reviewer_id: int | None = None,
        comment: str | None = None,
    ) -> "ProfileReview":
        from app.repositories import ProfileReviewRepository

        return ProfileReviewRepository().create(
            reviewee_user_id=reviewee_user_id,
            reviewer_name=reviewer_name,
            rating=rating,
            reviewer_id=reviewer_id,
            comment=comment,
        )
