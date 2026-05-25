from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .base_model import BaseModel


@dataclass
class Notification(BaseModel):
    id: int
    user_id: int
    message: str
    is_read: bool
    created_at: datetime

    @classmethod
    def from_row(cls, row: dict | None) -> Notification | None:
        if not row:
            return None
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            message=row["message"],
            is_read=bool(row["is_read"]),
            created_at=row["created_at"],
        )

    @classmethod
    def create(cls, user_id: int, message: str) -> int:
        from app.repositories import NotificationRepository
        return NotificationRepository().create(user_id, message)

    @classmethod
    def get_unread_count(cls, user_id: int) -> int:
        from app.repositories import NotificationRepository
        return NotificationRepository().get_unread_count(user_id)

    @classmethod
    def get_unread_notifications(cls, user_id: int) -> list[Notification]:
        from app.repositories import NotificationRepository
        return NotificationRepository().get_unread_notifications(user_id)
