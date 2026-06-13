from __future__ import annotations

from app.models.exchange import Exchange
from .base_repository import BaseRepository


class ExchangeRepository(BaseRepository):
    def create(self, *, request_id: int) -> Exchange:
        with self._db() as db:
            exchange_id = db.execute(
                """
                INSERT INTO exchanges (request_id, status)
                VALUES (%s, 'active')
                """,
                (request_id,),
            )
            row = db.fetch_one("SELECT * FROM exchanges WHERE id = %s", (exchange_id,))
        return Exchange.from_row(row)

    def find_by_id(self, exchange_id: int) -> Exchange | None:
        with self._db() as db:
            row = db.fetch_one("SELECT * FROM exchanges WHERE id = %s", (exchange_id,))
        return Exchange.from_row(row)

    def list_for_user(
        self,
        user_id: int,
        *,
        status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[Exchange]:
        query = """
            SELECT e.*
            FROM exchanges e
            JOIN exchange_requests er ON er.id = e.request_id
            JOIN skills s ON s.id = er.listing_id
            WHERE (er.learner_id = %s OR s.user_id = %s)
        """
        params: list = [user_id, user_id]
        if status:
            query += " AND e.status = %s"
            params.append(status)
        if date_from:
            query += " AND e.created_at >= %s"
            params.append(date_from)
        if date_to:
            query += " AND e.created_at < DATE_ADD(%s, INTERVAL 1 DAY)"
            params.append(date_to)
        query += " ORDER BY e.created_at DESC"
        with self._db() as db:
            rows = db.fetch_all(query, params)
        return [Exchange.from_row(row) for row in rows if row]

    def count(self) -> int:
        with self._db() as db:
            row = db.fetch_one("SELECT COUNT(*) AS count FROM exchanges")
        return int((row or {}).get("count") or 0)

    def find_by_request_id(self, request_id: int) -> Exchange | None:
        with self._db() as db:
            row = db.fetch_one("SELECT * FROM exchanges WHERE request_id = %s", (request_id,))
        return Exchange.from_row(row)

    def update_status(self, exchange_id: int, status: str, completed_at: datetime | None = None) -> None:
        with self._db() as db:
            db.execute(
                """
                UPDATE exchanges
                SET status = %s, completed_at = %s
                WHERE id = %s
                """,
                (status, completed_at, exchange_id),
            )
