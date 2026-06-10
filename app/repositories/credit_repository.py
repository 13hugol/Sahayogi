from __future__ import annotations

from app.models.credit_transaction import CreditTransaction, CreditHold
from .base_repository import BaseRepository


class CreditRepository(BaseRepository):
    def create_hold(self, user_id: int, request_id: int, amount: int) -> CreditHold:
        with self._db() as db:
            hold_id = db.execute(
                """
                INSERT INTO credit_holds (user_id, request_id, amount, status)
                VALUES (%s, %s, %s, 'active')
                """,
                (user_id, request_id, amount),
            )
            row = db.fetch_one("SELECT * FROM credit_holds WHERE id = %s", (hold_id,))
        return CreditHold.from_row(row)

    def get_hold_by_request_id(self, request_id: int) -> CreditHold | None:
        with self._db() as db:
            row = db.fetch_one("SELECT * FROM credit_holds WHERE request_id = %s AND status = 'active'", (request_id,))
        return CreditHold.from_row(row)

    def release_hold(self, request_id: int) -> None:
        with self._db() as db:
            db.execute(
                """
                UPDATE credit_holds
                SET status = 'released'
                WHERE request_id = %s AND status = 'active'
                """,
                (request_id,),
            )

    def clear_hold(self, request_id: int) -> None:
        with self._db() as db:
            db.execute(
                """
                UPDATE credit_holds
                SET status = 'cleared'
                WHERE request_id = %s AND status = 'active'
                """,
                (request_id,),
            )

    def create_transaction(
        self,
        user_id: int,
        amount_delta: int,
        entry_type: str,
        description: str,
        skill_id: int | None = None,
        exchange_id: int | None = None,
    ) -> CreditTransaction:
        with self._db() as db:
            with db.transaction():
                tx_id = db.execute(
                    """
                    INSERT INTO credit_transactions (user_id, amount_delta, entry_type, description, skill_id, exchange_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (user_id, amount_delta, entry_type, description, skill_id, exchange_id),
                )
                db.execute(
                    """
                    UPDATE users
                    SET credit_balance = credit_balance + %s
                    WHERE id = %s
                    """,
                    (amount_delta, user_id),
                )
                row = db.fetch_one("SELECT * FROM credit_transactions WHERE id = %s", (tx_id,))
        return CreditTransaction.from_row(row)

    def get_history_for_user(self, user_id: int) -> list[CreditTransaction]:
        with self._db() as db:
            rows = db.fetch_all(
                """
                SELECT * FROM credit_transactions
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
        return [CreditTransaction.from_row(row) for row in rows if row]

    def get_active_holds_for_user(self, user_id: int) -> list[CreditHold]:
        with self._db() as db:
            rows = db.fetch_all(
                """
                SELECT * FROM credit_holds
                WHERE user_id = %s AND status = 'active'
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
        return [CreditHold.from_row(row) for row in rows if row]
