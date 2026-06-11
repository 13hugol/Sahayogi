from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from app.models.base_model import BaseModel


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
        req = self.request
        return req.offered_skill if req else None

    @property
    def completion_marks(self) -> list:
        if self.status == "completed" and self.completed_at:
            from types import SimpleNamespace
            user_obj = self.teacher or self.learner
            return [SimpleNamespace(user=user_obj, completed_at=self.completed_at)]
        return []
