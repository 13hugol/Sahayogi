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
    learner_completed_at: datetime | None = None
    teacher_completed_at: datetime | None = None
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
            learner_completed_at=row.get("learner_completed_at"),
            teacher_completed_at=row.get("teacher_completed_at"),
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
    def conversation(self):
        request = self.request
        listing = self.listing
        if not request or not listing:
            return None
        from app.repositories.message_repository import MessageRepository
        return MessageRepository().find_between_users(request.learner_id, listing.user_id)

    def completed_by(self, user_id: int) -> datetime | None:
        request = self.request
        if request and user_id == request.learner_id:
            return self.learner_completed_at
        listing = self.listing
        if listing and user_id == listing.user_id:
            return self.teacher_completed_at
        return None

    @property
    def completion_marks(self) -> list:
        from types import SimpleNamespace

        marks = []
        if self.learner_completed_at:
            marks.append(SimpleNamespace(user=self.learner, completed_at=self.learner_completed_at))
        if self.teacher_completed_at:
            marks.append(SimpleNamespace(user=self.teacher, completed_at=self.teacher_completed_at))
        if not marks and self.status == "completed" and self.completed_at:
            user_obj = self.teacher or self.learner
            marks.append(SimpleNamespace(user=user_obj, completed_at=self.completed_at))
        return marks
