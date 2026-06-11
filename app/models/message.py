from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import SimpleNamespace

from .base_model import BaseModel


@dataclass
class MessagePost(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    body: str
    delivered_at: datetime | None = None
    read_at: datetime | None = None
    created_at: datetime | None = None
    sender_name: str | None = None

    @classmethod
    def from_row(cls, row: dict | None) -> "MessagePost | None":
        if not row:
            return None
        return cls(
            id=row["id"],
            conversation_id=row["conversation_id"],
            sender_id=row["sender_id"],
            body=row["body"],
            delivered_at=row.get("delivered_at"),
            read_at=row.get("read_at"),
            created_at=row.get("created_at"),
            sender_name=row.get("sender_name"),
        )

    @property
    def sender(self):
        if self.sender_name:
            return SimpleNamespace(id=self.sender_id, full_name=self.sender_name)
        from app.models.user import User

        return User.find_by_id(self.sender_id)


@dataclass
class MessageConversation(BaseModel):
    id: int
    subject: str
    permission_source: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    participants: list[SimpleNamespace] = field(default_factory=list)
    last_message: MessagePost | None = None
    unread_count: int = 0
    messages: list[MessagePost] = field(default_factory=list)

    @classmethod
    def from_row(cls, row: dict | None) -> "MessageConversation | None":
        if not row:
            return None
        return cls(
            id=row["id"],
            subject=row["subject"],
            permission_source=row["permission_source"],
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    def other_participant(self, user_id: int):
        for participant in self.participants:
            if participant.id != user_id:
                return participant
        return None
