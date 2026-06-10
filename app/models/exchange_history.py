from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace

from .base_model import BaseModel


def _optional_int(value) -> int | None:
    if value in {None, ""}:
        return None
    return int(value)


@dataclass
class ExchangeHistoryItem(BaseModel):
    id: int
    user_id: int
    listing_title: str
    exchange_type: str
    partner_name: str
    user_role: str
    status: str
    created_at: datetime
    updated_at: datetime | None = None
    listing_id: int | None = None
    completed_at: datetime | None = None
    declined_at: datetime | None = None
    conversation_id: int | None = None
    review_submitted: bool = False

    @classmethod
    def from_row(cls, row: dict | None) -> "ExchangeHistoryItem | None":
        if not row:
            return None
        return cls(
            id=int(row["id"]),
            user_id=int(row["user_id"]),
            listing_id=_optional_int(row.get("listing_id")),
            listing_title=row.get("listing_title") or "Skill exchange",
            exchange_type=row.get("exchange_type") or "credit",
            partner_name=row.get("partner_name") or "Exchange partner",
            user_role=row.get("user_role") or "member",
            status=row.get("status") or "pending",
            created_at=row["created_at"],
            updated_at=row.get("updated_at"),
            completed_at=row.get("completed_at"),
            declined_at=row.get("declined_at"),
            conversation_id=_optional_int(row.get("conversation_id")),
            review_submitted=bool(row.get("review_submitted")),
        )

    @property
    def can_review(self) -> bool:
        return self.status == "completed" and not self.review_submitted

    @property
    def listing(self):
        return SimpleNamespace(id=self.listing_id, title=self.listing_title)

    @property
    def teacher(self):
        if self.user_role == "teacher":
            return SimpleNamespace(full_name="You")
        return SimpleNamespace(full_name=self.partner_name)

    @property
    def learner(self):
        if self.user_role == "learner":
            return SimpleNamespace(full_name="You")
        return SimpleNamespace(full_name=self.partner_name)

    @property
    def conversation(self):
        if not self.conversation_id:
            return None
        return SimpleNamespace(id=self.conversation_id)

    @property
    def request(self):
        return SimpleNamespace(credits_reserved=0)

    @property
    def barter_skill(self):
        return None

    @property
    def completion_marks(self):
        if self.completed_at:
            return [SimpleNamespace(user=SimpleNamespace(full_name="Exchange member"), completed_at=self.completed_at)]
        return []
