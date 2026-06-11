from __future__ import annotations

from app.models.exchange import Exchange, ExchangeCompletionMark
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

    def list_for_user(self, user_id: int) -> list[Exchange]:
        with self._db() as db:
            rows = db.fetch_all(
                """
                SELECT e.*
                FROM exchanges e
                JOIN exchange_requests er ON er.id = e.request_id
                JOIN skills s ON s.id = er.listing_id
                WHERE er.learner_id = %s OR s.user_id = %s
                ORDER BY e.created_at DESC
                """,
                (user_id, user_id),
            )
        return [Exchange.from_row(row) for row in rows if row]

    def find_by_request_id(self, request_id: int) -> Exchange | None:
        with self._db() as db:
            row = db.fetch_one("SELECT * FROM exchanges WHERE request_id = %s", (request_id,))
        return Exchange.from_row(row)

    def is_participant(self, exchange_id: int, user_id: int) -> bool:
        with self._db() as db:
            row = db.fetch_one(
                """
                SELECT 1
                FROM exchanges e
                JOIN exchange_requests er ON er.id = e.request_id
                JOIN skills s ON s.id = er.listing_id
                WHERE e.id = %s
                  AND (er.learner_id = %s OR s.user_id = %s)
                """,
                (exchange_id, user_id, user_id),
            )
        return row is not None

    def participant_ids(self, exchange_id: int) -> tuple[int, int] | None:
        with self._db() as db:
            row = db.fetch_one(
                """
                SELECT er.learner_id, s.user_id AS teacher_id
                FROM exchanges e
                JOIN exchange_requests er ON er.id = e.request_id
                JOIN skills s ON s.id = er.listing_id
                WHERE e.id = %s
                """,
                (exchange_id,),
            )
        if not row:
            return None
        return int(row["learner_id"]), int(row["teacher_id"])

    def mark_complete(self, *, exchange_id: int, user_id: int) -> Exchange:
        with self._db() as db:
            with db.transaction():
                exchange_row = db.fetch_one("SELECT * FROM exchanges WHERE id = %s", (exchange_id,))
                db.execute(
                    """
                    INSERT IGNORE INTO exchange_completion_marks (exchange_id, user_id)
                    VALUES (%s, %s)
                    """,
                    (exchange_id, user_id),
                )
                participant_row = db.fetch_one(
                    """
                    SELECT er.learner_id, s.user_id AS teacher_id
                    FROM exchanges e
                    JOIN exchange_requests er ON er.id = e.request_id
                    JOIN skills s ON s.id = er.listing_id
                    WHERE e.id = %s
                    """,
                    (exchange_id,),
                )
                mark_rows = db.fetch_all(
                    """
                    SELECT user_id
                    FROM exchange_completion_marks
                    WHERE exchange_id = %s
                    """,
                    (exchange_id,),
                )
                participant_ids = None
                if participant_row:
                    participant_ids = (int(participant_row["learner_id"]), int(participant_row["teacher_id"]))
                if (
                    exchange_row
                    and exchange_row["status"] != "completed"
                    and participant_ids
                    and {int(row["user_id"]) for row in mark_rows} >= set(participant_ids)
                ):
                    db.execute(
                        """
                        UPDATE exchanges
                        SET status = 'completed',
                            completed_at = COALESCE(completed_at, CURRENT_TIMESTAMP)
                        WHERE id = %s
                        """,
                        (exchange_id,),
                    )
                    for participant_id in participant_ids:
                        db.execute(
                            """
                            UPDATE profiles
                            SET completed_exchange_count = completed_exchange_count + 1
                            WHERE user_id = %s
                            """,
                            (participant_id,),
                        )
                row = db.fetch_one("SELECT * FROM exchanges WHERE id = %s", (exchange_id,))
        return Exchange.from_row(row)

    def completion_marks(self, exchange_id: int) -> list[ExchangeCompletionMark]:
        with self._db() as db:
            rows = db.fetch_all(
                """
                SELECT *
                FROM exchange_completion_marks
                WHERE exchange_id = %s
                ORDER BY completed_at ASC, id ASC
                """,
                (exchange_id,),
            )
        return [mark for row in rows if (mark := ExchangeCompletionMark.from_row(row))]

    def is_fully_completed(self, exchange_id: int) -> bool:
        exchange = self.find_by_id(exchange_id)
        if not exchange or exchange.status != "completed":
            return False
        participant_ids = self.participant_ids(exchange_id)
        if not participant_ids:
            return False
        return {mark.user_id for mark in self.completion_marks(exchange_id)} >= set(participant_ids)
