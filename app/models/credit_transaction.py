from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from app.models.base_model import BaseModel


@dataclass
class CreditTransaction(BaseModel):
    id: int
    user_id: int
    amount_delta: int
    entry_type: str
    description: str
    skill_id: int | None = None
    exchange_id: int | None = None
    created_at: datetime | None = None

    @classmethod
    def from_row(cls, row: dict | None) -> CreditTransaction | None:
        if not row:
            return None
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            amount_delta=row["amount_delta"],
            entry_type=row["entry_type"],
            description=row["description"],
            skill_id=row.get("skill_id"),
            exchange_id=row.get("exchange_id"),
            created_at=row.get("created_at"),
        )


@dataclass
class CreditHold(BaseModel):
    id: int
    user_id: int
    request_id: int
    amount: int
    status: str
    created_at: datetime | None = None

    @classmethod
    def from_row(cls, row: dict | None) -> CreditHold | None:
        if not row:
            return None
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            request_id=row["request_id"],
            amount=row["amount"],
            status=row["status"],
            created_at=row.get("created_at"),
        )
