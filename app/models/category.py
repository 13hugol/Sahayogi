from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .base_model import BaseModel


@dataclass
class Category(BaseModel):
    id: int
    name: str
    slug: str
    icon: str
    description: str
    sort_order: int = 0
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_row(cls, row: dict | None) -> "Category | None":
        if not row:
            return None
        return cls(
            id=int(row["id"]),
            name=row["name"],
            slug=row["slug"],
            icon=row.get("icon") or "CAT",
            description=row.get("description") or "",
            sort_order=int(row.get("sort_order") or 0),
            is_active=bool(row.get("is_active", True)),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

