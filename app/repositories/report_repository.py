from __future__ import annotations

from datetime import datetime, timedelta
from app.models.report import Report
from .base_repository import BaseRepository


class ReportRepository(BaseRepository):
    def create(
        self,
        reporter_id: int,
        reported_user_id: int,
        reason: str,
        description: str | None = None,
    ) -> int:
        with self._db() as db:
            report_id = db.execute(
                """
                INSERT INTO reports (reporter_id, reported_user_id, reason, description)
                VALUES (%s, %s, %s, %s)
                """,
                (reporter_id, reported_user_id, reason, description),
            )
        return report_id

    def has_recent_report(
        self, reporter_id: int, reported_user_id: int, within_days: int = 7
    ) -> bool:
        cutoff = datetime.utcnow() - timedelta(days=within_days)
        with self._db() as db:
            row = db.fetch_one(
                """
                SELECT id FROM reports 
                WHERE reporter_id = %s 
                  AND reported_user_id = %s 
                  AND created_at >= %s
                """,
                (reporter_id, reported_user_id, cutoff),
            )
        return row is not None

    def list_all(self) -> list[Report]:
        with self._db() as db:
            rows = db.fetch_all("SELECT * FROM reports ORDER BY created_at DESC")
        return [Report.from_row(row) for row in rows if row]

    def update_status(self, report_id: int, status: str) -> None:
        with self._db() as db:
            db.execute(
                "UPDATE reports SET status = %s WHERE id = %s",
                (status, report_id),
            )

    def find_by_id(self, report_id: int) -> Report | None:
        with self._db() as db:
            row = db.fetch_one("SELECT * FROM reports WHERE id = %s", (report_id,))
        return Report.from_row(row)
