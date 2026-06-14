from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .base_model import BaseModel


@dataclass
class Notification(BaseModel):
    id: int
    user_id: int
    body: str = ""
    title: str = ""
    event_type: str = "general"
    target_url: str | None = None
    is_read: bool = False
    created_at: datetime | None = None
    read_at: datetime | None = None
    message: str = field(default="", repr=False)

    @classmethod
    def from_row(cls, row: dict[str, Any] | None) -> "Notification | None":
        if not row:
            return None
        body = row.get("body") or row.get("message") or ""
        title = row.get("title") or (body[:80] if body else "Notification")
        message = row.get("message") or body
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            body=body,
            title=title,
            event_type=row.get("event_type") or "general",
            target_url=row.get("target_url"),
            is_read=bool(row.get("is_read")),
            created_at=row.get("created_at"),
            read_at=row.get("read_at"),
            message=message,
        )

    @property
    def url(self) -> str | None:
        return self.target_url

    @property
    def display_title(self) -> str:
        return self.title or (self.body[:80] if self.body else "Notification")

    @property
    def display_body(self) -> str:
        return self.body or self.message

    @classmethod
    def create(
        cls,
        user_id: int,
        message: str | None = None,
        *,
        title: str | None = None,
        body: str | None = None,
        event_type: str = "general",
        target_url: str | None = None,
    ) -> int:
        from app.repositories import NotificationRepository

        text = body or message or ""
        title_text = title or text[:80] or "Notification"
        return NotificationRepository().create(
            user_id=user_id,
            event_type=event_type,
            title=title_text,
            body=text,
            target_url=target_url,
        )

    @classmethod
    def create_new_match_notification(
        cls,
        recipient_user_id: int,
        matched_user_name: str,
        matched_user_id: int,
    ) -> int:
        from app.repositories import NotificationRepository

        return NotificationRepository().create(
            user_id=recipient_user_id,
            event_type="new_match",
            title="New mutual match",
            body=f"You have a new mutual skill match with {matched_user_name}!",
            target_url=f"/matches#match-{matched_user_id}",
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
    def get_unread_notifications(cls, user_id: int) -> list["Notification"]:
        from app.repositories import NotificationRepository

        return NotificationRepository().get_unread_notifications(user_id)
