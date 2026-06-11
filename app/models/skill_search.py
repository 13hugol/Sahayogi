from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

from .base_model import BaseModel


@dataclass
class SkillSearchListing(BaseModel):
    id: int
    title: str
    description: str
    skill_id: int
    skill: SimpleNamespace
    category: SimpleNamespace
    user_id: int | None
    user: SimpleNamespace
    exchange_type: str
    min_credits: int
    location_text: str | None = None
    contact_method: str | None = None
    status: str = "approved"
    availability: list = field(default_factory=list)

    @classmethod
    def from_row(cls, row: dict | None) -> "SkillSearchListing | None":
        if not row:
            return None
        profile = SimpleNamespace(
            location=row.get("provider_location"),
            contact_email=None,
            reputation_score=float(row.get("reputation_score") or 0),
        )
        user = SimpleNamespace(
            id=row.get("user_id"),
            full_name=row.get("provider_name") or "Sahayogi Member",
            profile=profile,
            has_verified_skill=lambda _skill_id: False,
        )
        return cls(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            skill_id=row["id"],
            skill=SimpleNamespace(id=row["id"], name=row["skill_name"]),
            category=SimpleNamespace(id=row.get("category_id"), name=row["category_name"]),
            user_id=row.get("user_id"),
            user=user,
            exchange_type=row.get("exchange_type") or "credit",
            min_credits=int(row.get("min_credits") or 0),
            location_text=row.get("location_text"),
            contact_method=row.get("contact_method"),
            status=row.get("status") or "approved",
        )
