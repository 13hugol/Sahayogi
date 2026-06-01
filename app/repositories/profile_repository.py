from __future__ import annotations

from app.dto import TopRatedProfile
from app.enums import CertificateStatus, SkillType
from app.exceptions import InvalidSkillTypeError
from app.models.profile import ProfileCertificate, ProfileReview, ProfileSkill
from app.models.user import Profile

from .base_repository import BaseRepository


class ProfileRepository(BaseRepository):
    def find_by_user_id(self, user_id: int) -> Profile | None:
        with self._db() as db:
            row = db.fetch_one("SELECT * FROM profiles WHERE user_id = %s", (user_id,))
        return Profile.from_row(row)

    def create(self, user_id: int, username: str, location: str, contact_email: str) -> None:
        with self._db() as db:
            db.execute(
                """
                INSERT INTO profiles (user_id, username, location, contact_email)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, username, location, contact_email),
            )

    def username_exists(self, username: str) -> bool:
        with self._db() as db:
            row = db.fetch_one("SELECT user_id FROM profiles WHERE username = %s", (username,))
        return row is not None

    def top_rated(self, limit: int = 12) -> list[TopRatedProfile]:
        with self._db() as db:
            rows = db.fetch_all(
                """
                SELECT profiles.*, users.full_name
                FROM profiles
                INNER JOIN users ON users.id = profiles.user_id
                WHERE profiles.review_count >= 3
                ORDER BY profiles.reputation_score DESC, profiles.review_count DESC, profiles.user_id ASC
                LIMIT %s
                """,
                (limit,),
            )
        return [
            TopRatedProfile(
                user_id=row["user_id"],
                full_name=row["full_name"],
                username=row["username"],
                reputation_score=float(row.get("reputation_score") or 0),
                review_count=int(row.get("review_count") or 0),
                completed_exchange_count=int(row.get("completed_exchange_count") or 0),
            )
            for row in rows
        ]


class ProfileSkillRepository(BaseRepository):
    def find_for_user(self, user_id: int, skill_type: str | SkillType) -> list[ProfileSkill]:
        normalized_type = self._normalize_skill_type(skill_type)
        with self._db() as db:
            rows = db.fetch_all(
                """
                SELECT
                    profile_skills.*,
                    EXISTS (
                        SELECT 1
                        FROM profile_certificates
                        WHERE profile_certificates.profile_skill_id = profile_skills.id
                          AND profile_certificates.status = %s
                    ) AS has_verified_certificate
                FROM profile_skills
                WHERE user_id = %s AND skill_type = %s
                ORDER BY sort_order ASC, skill_name ASC
                """,
                (CertificateStatus.APPROVED.value, user_id, normalized_type),
            )
        return [skill for row in rows if (skill := ProfileSkill.from_row(row))]

    def find_by_id(self, skill_id: int) -> ProfileSkill | None:
        with self._db() as db:
            row = db.fetch_one(
                """
                SELECT
                    profile_skills.*,
                    EXISTS (
                        SELECT 1
                        FROM profile_certificates
                        WHERE profile_certificates.profile_skill_id = profile_skills.id
                          AND profile_certificates.status = %s
                    ) AS has_verified_certificate
                FROM profile_skills
                WHERE id = %s
                """,
                (CertificateStatus.APPROVED.value, skill_id),
            )
        return ProfileSkill.from_row(row)

    def create(self, user_id: int, skill_name: str, skill_type: str | SkillType, sort_order: int = 0) -> ProfileSkill:
        normalized_type = self._normalize_skill_type(skill_type)
        with self._db() as db:
            skill_id = db.execute(
                """
                INSERT INTO profile_skills (user_id, skill_name, skill_type, sort_order)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, skill_name.strip(), normalized_type, sort_order),
            )
            row = db.fetch_one("SELECT * FROM profile_skills WHERE id = %s", (skill_id,))
        return ProfileSkill.from_row(row)

    @staticmethod
    def _normalize_skill_type(skill_type: str | SkillType) -> str:
        if isinstance(skill_type, SkillType):
            return skill_type.value
        normalized_type = str(skill_type).strip().lower()
        if normalized_type not in SkillType.values():
            raise InvalidSkillTypeError(normalized_type)
        return normalized_type


class ProfileCertificateRepository(BaseRepository):
    def approved_for_user(self, user_id: int) -> list[ProfileCertificate]:
        with self._db() as db:
            rows = db.fetch_all(
                """
                SELECT *
                FROM profile_certificates
                WHERE user_id = %s AND status = %s
                ORDER BY created_at DESC, skill_name ASC
                """,
                (user_id, CertificateStatus.APPROVED.value),
            )
        return [certificate for row in rows if (certificate := ProfileCertificate.from_row(row))]

    def create(
        self,
        *,
        user_id: int,
        skill_name: str,
        profile_skill_id: int | None = None,
        status: str = CertificateStatus.PENDING.value,
        file_path: str | None = None,
        review_notes: str | None = None,
    ) -> ProfileCertificate:
        with self._db() as db:
            certificate_id = db.execute(
                """
                INSERT INTO profile_certificates
                    (user_id, profile_skill_id, skill_name, status, file_path, review_notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (user_id, profile_skill_id, skill_name.strip(), status, file_path, review_notes),
            )
            row = db.fetch_one("SELECT * FROM profile_certificates WHERE id = %s", (certificate_id,))
        return ProfileCertificate.from_row(row)


class ProfileReviewRepository(BaseRepository):
    def recent_for_user(self, user_id: int, limit: int = 3) -> list[ProfileReview]:
        with self._db() as db:
            rows = db.fetch_all(
                """
                SELECT *
                FROM profile_reviews
                WHERE reviewee_user_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
        return [review for row in rows if (review := ProfileReview.from_row(row))]

    def for_user(self, user_id: int) -> list[ProfileReview]:
        with self._db() as db:
            rows = db.fetch_all(
                """
                SELECT *
                FROM profile_reviews
                WHERE reviewee_user_id = %s
                ORDER BY created_at DESC, id DESC
                """,
                (user_id,),
            )
        return [review for row in rows if (review := ProfileReview.from_row(row))]

    def create(
        self,
        *,
        reviewee_user_id: int,
        reviewer_name: str,
        rating: int,
        reviewer_id: int | None = None,
        comment: str | None = None,
    ) -> ProfileReview:
        with self._db() as db:
            review_id = db.execute(
                """
                INSERT INTO profile_reviews
                    (reviewee_user_id, reviewer_id, reviewer_name, rating, comment)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (reviewee_user_id, reviewer_id, reviewer_name.strip(), rating, comment),
            )
            row = db.fetch_one("SELECT * FROM profile_reviews WHERE id = %s", (review_id,))
        return ProfileReview.from_row(row)

