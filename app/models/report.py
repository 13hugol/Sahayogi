from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .base_model import BaseModel
from .user import User


@dataclass
class Report(BaseModel):
    id: int
    reporter_id: int
    reported_user_id: int
    reason: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    @property
    def reporter(self) -> User | None:
        return User.find_by_id(self.reporter_id)

    @property
    def reported_user(self) -> User | None:
        return User.find_by_id(self.reported_user_id)

    @classmethod
    def from_row(cls, row: dict | None) -> Report | None:
        if not row:
            return None
        return cls(
            id=row["id"],
            reporter_id=row["reporter_id"],
            reported_user_id=row["reported_user_id"],
            reason=row["reason"],
            description=row.get("description"),
            status=row.get("status", "open"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
