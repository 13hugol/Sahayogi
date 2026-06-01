from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from app.models.base_model import BaseModel


@dataclass
class ExchangeRequest(BaseModel):
    id: int
    listing_id: int
    learner_id: int
    offered_skill_id: int | None
    requested_message: str | None
    status: str
    decline_reason: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_row(cls, row: dict | None) -> ExchangeRequest | None:
        if not row:
            return None
        return cls(
            id=row["id"],
            listing_id=row["listing_id"],
            learner_id=row["learner_id"],
            offered_skill_id=row.get("offered_skill_id"),
            requested_message=row.get("requested_message"),
            status=row["status"],
            decline_reason=row.get("decline_reason"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    @property
    def learner(self):
        from app.models.user import User
        return User.find_by_id(self.learner_id)

    @property
    def sender(self):
        return self.learner

    @property
    def listing(self):
        from app.models.skill import Skill
        from app.repositories.skill_repository import SkillRepository
        return SkillRepository().find_by_id(self.listing_id)

    @property
    def recipient(self):
        listing = self.listing
        if not listing:
            return None
        from app.models.user import User
        return User.find_by_id(listing.user_id)

    @property
    def offered_skill(self):
        if not self.offered_skill_id:
            return None
        from app.models.profile import ProfileSkill
        from app.repositories.profile_repository import ProfileSkillRepository
        return ProfileSkillRepository().find_by_id(self.offered_skill_id)

    @property
    def request_type(self) -> str:
        # returns 'teach' (barter) or 'credit' based on listing
        listing = self.listing
        return listing.exchange_type if listing else 'credit'

    @property
    def credits_reserved(self) -> int:
        listing = self.listing
        if listing and listing.exchange_type == 'credit':
            return listing.credit_cost
        return 0
