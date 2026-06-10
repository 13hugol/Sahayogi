from __future__ import annotations

from datetime import date, datetime, time, timedelta

from app.models import ExchangeHistoryItem

from .base_repository import BaseRepository


class ExchangeHistoryRepository(BaseRepository):
    def list_for_user(
        self,
        user_id: int,
        *,
        status: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> list[ExchangeHistoryItem]:
        where_clauses = ["user_id = %s"]
        params: list = [user_id]
        if status:
            where_clauses.append("status = %s")
            params.append(status)
        if start_date:
            where_clauses.append("created_at >= %s")
            params.append(datetime.combine(start_date, time.min))
        if end_date:
            where_clauses.append("created_at < %s")
            params.append(datetime.combine(end_date + timedelta(days=1), time.min))

        query = f"""
            SELECT *
            FROM exchange_history_items
            WHERE {" AND ".join(where_clauses)}
            ORDER BY created_at DESC, id DESC
        """
        if limit:
            query += " LIMIT %s"
            params.append(limit)

        with self._db() as db:
            rows = db.fetch_all(query, tuple(params))
        return [item for row in rows if (item := ExchangeHistoryItem.from_row(row))]

    def count_for_user(self, user_id: int) -> int:
        with self._db() as db:
            row = db.fetch_one(
                "SELECT COUNT(*) AS count FROM exchange_history_items WHERE user_id = %s",
                (user_id,),
            )
        return int((row or {}).get("count") or 0)

    def find_for_user(self, user_id: int, exchange_id: int) -> ExchangeHistoryItem | None:
        with self._db() as db:
            row = db.fetch_one(
                """
                SELECT *
                FROM exchange_history_items
                WHERE user_id = %s AND id = %s
                """,
                (user_id, exchange_id),
            )
        return ExchangeHistoryItem.from_row(row)
