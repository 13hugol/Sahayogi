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
    type: str = "general"
    target_url: str | None = None

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
            type=row.get("type", "general"),
            target_url=row.get("target_url"),
        )

    @classmethod
    def create(cls, user_id: int, message: str, type: str = "general", target_url: str | None = None) -> int:
        from app.repositories import NotificationRepository
        return NotificationRepository().create(user_id, message, type, target_url)

    @classmethod
    def create_new_match_notification(cls, recipient_user_id: int, matched_user_name: str, matched_user_id: int) -> None:
        from app.repositories import NotificationRepository
        NotificationRepository().create(
            user_id=recipient_user_id,
            message=f"You have a new mutual skill match with {matched_user_name}!",
            type="new_match",
            target_url=f"/matches#match-{matched_user_id}"
        )

    @classmethod
    def get_notified_match_ids(cls, user_id: int) -> list[int]:
        from app.repositories import NotificationRepository
        return NotificationRepository().get_notified_match_ids(user_id)

    @classmethod
    def get_unread_count(cls, user_id: int) -> int:
        from app.repositories import NotificationRepository
        return NotificationRepository().get_unread_count(user_id)

    @classmethod
    def get_unread_notifications(cls, user_id: int) -> list[Notification]:
        from app.repositories import NotificationRepository
        return NotificationRepository().get_unread_notifications(user_id)
