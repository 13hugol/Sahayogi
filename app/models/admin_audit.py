from __future__ import annotations

from dataclasses import dataclass

from .base_model import BaseModel


@dataclass
class AdminAuditLog(BaseModel):
    id: int
    admin_id: int
    action: str
    target_type: str
    target_id: int | None
    detail: str | None

    @classmethod
    def from_row(cls, row: dict | None) -> "AdminAuditLog | None":
        if not row:
            return None
        return cls(
            id=row["id"],
            admin_id=row["admin_id"],
            action=row["action"],
            target_type=row["target_type"],
            target_id=row.get("target_id"),
            detail=row.get("detail"),
        )

    @classmethod
    def create(
        cls,
        *,
        admin_id: int,
        action: str,
        target_type: str,
        target_id: int | None = None,
        detail: str | None = None,
    ) -> None:
        from app.repositories import AdminAuditRepository

        AdminAuditRepository().create(
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )

    @classmethod
    def count(cls) -> int:
        from app.repositories import AdminAuditRepository

        return AdminAuditRepository().count()

    @classmethod
    def find_by_action(cls, action: str) -> "AdminAuditLog | None":
        from app.repositories import AdminAuditRepository

        return AdminAuditRepository().find_by_action(action)
