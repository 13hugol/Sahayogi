from __future__ import annotations

from app.models.exchange_request import ExchangeRequest
from .base_repository import BaseRepository


class ExchangeRequestRepository(BaseRepository):
    def create(
        self,
        *,
        listing_id: int,
        learner_id: int,
        offered_skill_id: int | None = None,
        requested_message: str | None = None,
    ) -> ExchangeRequest:
        with self._db() as db:
            request_id = db.execute(
                """
                INSERT INTO exchange_requests (listing_id, learner_id, offered_skill_id, requested_message, status)
                VALUES (%s, %s, %s, %s, 'pending')
                """,
                (listing_id, learner_id, offered_skill_id, requested_message),
            )
            row = db.fetch_one("SELECT * FROM exchange_requests WHERE id = %s", (request_id,))
        return ExchangeRequest.from_row(row)

    def find_by_id(self, request_id: int) -> ExchangeRequest | None:
        with self._db() as db:
            row = db.fetch_one("SELECT * FROM exchange_requests WHERE id = %s", (request_id,))
        return ExchangeRequest.from_row(row)

    def list_incoming_pending(self, teacher_id: int) -> list[ExchangeRequest]:
        with self._db() as db:
            rows = db.fetch_all(
                """
                SELECT er.*
                FROM exchange_requests er
                JOIN skills s ON s.id = er.listing_id
                WHERE s.user_id = %s AND er.status = 'pending'
                ORDER BY er.created_at DESC
                """,
                (teacher_id,),
            )
        return [ExchangeRequest.from_row(row) for row in rows if row]

    def list_incoming_history(self, teacher_id: int) -> list[ExchangeRequest]:
        with self._db() as db:
            rows = db.fetch_all(
                """
                SELECT er.*
                FROM exchange_requests er
                JOIN skills s ON s.id = er.listing_id
                WHERE s.user_id = %s AND er.status <> 'pending'
                ORDER BY er.updated_at DESC, er.id DESC
                """,
                (teacher_id,),
            )
        return [ExchangeRequest.from_row(row) for row in rows if row]

    def list_sent(self, learner_id: int) -> list[ExchangeRequest]:
        with self._db() as db:
            rows = db.fetch_all(
                """
                SELECT * FROM exchange_requests
                WHERE learner_id = %s
                ORDER BY created_at DESC
                """,
                (learner_id,),
            )
        return [ExchangeRequest.from_row(row) for row in rows if row]

    def update_status(self, request_id: int, status: str, decline_reason: str | None = None) -> None:
        with self._db() as db:
            db.execute(
                """
                UPDATE exchange_requests
                SET status = %s, decline_reason = %s
                WHERE id = %s
                """,
                (status, decline_reason, request_id),
            )
