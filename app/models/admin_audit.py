from __future__ import annotations

from dataclasses import dataclass

from app.database import Database
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
    def create(
        cls,
        *,
        admin_id: int,
        action: str,
        target_type: str,
        target_id: int | None = None,
        detail: str | None = None,
    ) -> None:
        db = Database()
        try:
            db.execute(
                """
                INSERT INTO admin_audit_logs (admin_id, action, target_type, target_id, detail)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (admin_id, action, target_type, target_id, detail),
            )
        finally:
            db.close()

    @classmethod
    def count(cls) -> int:
        db = Database()
        try:
            row = db.fetch_one("SELECT COUNT(*) AS count FROM admin_audit_logs")
            return int(row["count"])
        finally:
            db.close()

    @classmethod
    def find_by_action(cls, action: str) -> "AdminAuditLog | None":
        db = Database()
        try:
            row = db.fetch_one(
                "SELECT * FROM admin_audit_logs WHERE action = %s ORDER BY created_at DESC LIMIT 1",
                (action,),
            )
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
        finally:
            db.close()
