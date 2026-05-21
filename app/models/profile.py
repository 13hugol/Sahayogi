from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace

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
    def find_for_user(cls, user_id: int, skill_type: str) -> list["ProfileSkill"]:
        db = cls.db()
        try:
            rows = db.fetch_all(
                """
                SELECT
                    profile_skills.*,
                    EXISTS (
                        SELECT 1
                        FROM profile_certificates
                        WHERE profile_certificates.profile_skill_id = profile_skills.id
                          AND profile_certificates.status = 'approved'
                    ) AS has_verified_certificate
                FROM profile_skills
                WHERE user_id = %s AND skill_type = %s
                ORDER BY sort_order ASC, skill_name ASC
                """,
                (user_id, skill_type),
            )
            return [skill for row in rows if (skill := cls.from_row(row))]
        finally:
            db.close()

    @classmethod
    def create(cls, user_id: int, skill_name: str, skill_type: str, sort_order: int = 0) -> "ProfileSkill":
        if skill_type not in {"offered", "wanted"}:
            raise ValueError("Profile skill type must be 'offered' or 'wanted'.")
        db = cls.db()
        try:
            skill_id = db.execute(
                """
                INSERT INTO profile_skills (user_id, skill_name, skill_type, sort_order)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, skill_name.strip(), skill_type, sort_order),
            )
            row = db.fetch_one("SELECT * FROM profile_skills WHERE id = %s", (skill_id,))
            return cls.from_row(row)
        finally:
            db.close()


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
        db = cls.db()
        try:
            rows = db.fetch_all(
                """
                SELECT *
                FROM profile_certificates
                WHERE user_id = %s AND status = 'approved'
                ORDER BY created_at DESC, skill_name ASC
                """,
                (user_id,),
            )
            return [certificate for row in rows if (certificate := cls.from_row(row))]
        finally:
            db.close()

    @classmethod
    def create(
        cls,
        *,
        user_id: int,
        skill_name: str,
        profile_skill_id: int | None = None,
        status: str = "pending",
        file_path: str | None = None,
        review_notes: str | None = None,
    ) -> "ProfileCertificate":
        db = cls.db()
        try:
            certificate_id = db.execute(
                """
                INSERT INTO profile_certificates
                    (user_id, profile_skill_id, skill_name, status, file_path, review_notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (user_id, profile_skill_id, skill_name.strip(), status, file_path, review_notes),
            )
            row = db.fetch_one("SELECT * FROM profile_certificates WHERE id = %s", (certificate_id,))
            return cls.from_row(row)
        finally:
            db.close()


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
        db = cls.db()
        try:
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
            return [review for row in rows if (review := cls.from_row(row))]
        finally:
            db.close()

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
        db = cls.db()
        try:
            review_id = db.execute(
                """
                INSERT INTO profile_reviews
                    (reviewee_user_id, reviewer_id, reviewer_name, rating, comment)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (reviewee_user_id, reviewer_id, reviewer_name.strip(), rating, comment),
            )
            row = db.fetch_one("SELECT * FROM profile_reviews WHERE id = %s", (review_id,))
            return cls.from_row(row)
        finally:
            db.close()
