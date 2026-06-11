from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace

from app.models.base_model import BaseModel


@dataclass
class ExchangeCompletionMark(BaseModel):
    id: int
    exchange_id: int
    user_id: int
    completed_at: datetime | None = None

    @classmethod
    def from_row(cls, row: dict | None) -> "ExchangeCompletionMark | None":
        if not row:
            return None
        return cls(
            id=row["id"],
            exchange_id=row["exchange_id"],
            user_id=row["user_id"],
            completed_at=row.get("completed_at"),
        )

    @property
    def user(self):
        from app.models.user import User

        return User.find_by_id(self.user_id) or SimpleNamespace(id=self.user_id, full_name="Member")


@dataclass
class Exchange(BaseModel):
    id: int
    request_id: int
    status: str
    created_at: datetime | None = None
    completed_at: datetime | None = None
    video_session_summary: str | None = None

    @classmethod
    def from_row(cls, row: dict | None) -> Exchange | None:
        if not row:
            return None
        return cls(
            id=row["id"],
            request_id=row["request_id"],
            status=row["status"],
            created_at=row.get("created_at"),
            completed_at=row.get("completed_at"),
            video_session_summary=row.get("video_session_summary"),
        )

    @property
    def request(self):
        from app.repositories.exchange_request_repository import ExchangeRequestRepository
        return ExchangeRequestRepository().find_by_id(self.request_id)

    @property
    def listing(self):
        request = self.request
        return request.listing if request else None

    @property
    def learner(self):
        request = self.request
        return request.learner if request else None

    @property
    def teacher(self):
        listing = self.listing
        if not listing:
            return None
        from app.models.user import User
        return User.find_by_id(listing.user_id)

    @property
    def exchange_type(self) -> str:
        listing = self.listing
        return listing.exchange_type if listing else "credit"

    @property
    def barter_skill(self):
        request = self.request
        return request.offered_skill if request else None

    @property
    def completion_marks(self) -> list[ExchangeCompletionMark]:
        from app.repositories.exchange_repository import ExchangeRepository

        return ExchangeRepository().completion_marks(self.id)

    @property
    def conversation(self):
        return None
