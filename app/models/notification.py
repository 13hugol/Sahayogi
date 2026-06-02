from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .base_model import BaseModel


@dataclass
class Notification(BaseModel):
    id: int
    user_id: int
    event_type: str
    title: str
    body: str
    target_url: str | None = None
    is_read: bool = False
    created_at: datetime | None = None

    @classmethod
    def from_row(cls, row: dict | None) -> "Notification | None":
        if not row:
            return None
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            event_type=row["event_type"],
            title=row["title"],
            body=row["body"],
            target_url=row.get("target_url"),
            is_read=bool(row.get("is_read")),
            created_at=row.get("created_at"),
        )

    @property
    def url(self) -> str | None:
        return self.target_url
