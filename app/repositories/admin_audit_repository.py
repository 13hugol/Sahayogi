from __future__ import annotations

from app.models.admin_audit import AdminAuditLog

from .base_repository import BaseRepository


class AdminAuditRepository(BaseRepository):
    def create(
        self,
        *,
        admin_id: int,
        action: str,
        target_type: str,
        target_id: int | None = None,
        detail: str | None = None,
    ) -> None:
        with self._db() as db:
            db.execute(
                """
                INSERT INTO admin_audit_logs (admin_id, action, target_type, target_id, detail)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (admin_id, action, target_type, target_id, detail),
            )

    def count(self) -> int:
        with self._db() as db:
            row = db.fetch_one("SELECT COUNT(*) AS count FROM admin_audit_logs")
        return int((row or {}).get("count") or 0)

    def find_by_action(self, action: str) -> AdminAuditLog | None:
        with self._db() as db:
            row = db.fetch_one(
                "SELECT * FROM admin_audit_logs WHERE action = %s ORDER BY created_at DESC LIMIT 1",
                (action,),
            )
        return AdminAuditLog.from_row(row)

