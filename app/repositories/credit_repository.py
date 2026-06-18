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

    def has_active_hold_for_request(self, request_id: int) -> bool:
        """True if an active hold already exists for the given request.

        Used to guard against a learner creating duplicate active holds for the
        same exchange request, e.g. from a double-submitted form.
        """
        with self._db() as db:
            row = db.fetch_one(
                """
                SELECT id FROM credit_holds
                WHERE request_id = %s AND status = 'active'
                LIMIT 1
                """,
                (request_id,),
            )
        return row is not None

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

    def exchange_already_settled(self, exchange_id: int) -> bool:
        """True if credit settlement has already been recorded for an exchange.

        Guarantees idempotency: if both users refresh/resubmit the completion
        form, credits move exactly once.
        """
        with self._db() as db:
            row = db.fetch_one(
                """
                SELECT id FROM credit_transactions
                WHERE exchange_id = %s
                LIMIT 1
                """,
                (exchange_id,),
            )
        return row is not None

    def settle_exchange_credits(
        self,
        *,
        exchange_id: int,
        learner_id: int,
        teacher_id: int,
        listing_id: int,
        skill_title: str,
        amount: int,
    ) -> tuple[CreditTransaction, CreditTransaction]:
        """Atomically settle credit transfer when an exchange completes.

        In a single database transaction this:
        - clears the learner's active hold for the request,
        - debits the learner and credits the teacher,
        - writes both double-entry ledger rows, and
        - increments each participant's completed exchange count.

        Because the whole operation runs inside one transaction, the debit,
        credit, and ledger rows succeed together or fail together, as required
        by the guide's credit-transfer rule.
        """
        deduction = f"Spent {amount} credits on learning '{skill_title}'"
        earning = f"Earned {amount} credits from teaching '{skill_title}'"
        with self._db() as db:
            with db.transaction():
                # Re-check settlement inside the transaction to close the race
                # window if two completion requests arrive concurrently.
                already = db.fetch_one(
                    "SELECT id FROM credit_transactions WHERE exchange_id = %s LIMIT 1",
                    (exchange_id,),
                )
                if already:
                    row = db.fetch_one(
                        "SELECT * FROM credit_transactions WHERE exchange_id = %s ORDER BY id ASC",
                        (exchange_id,),
                    )
                    return (CreditTransaction.from_row(row), CreditTransaction.from_row(row))

                db.execute(
                    """
                    UPDATE credit_holds
                    SET status = 'cleared'
                    WHERE user_id = %s
                      AND request_id IN (
                          SELECT request_id FROM exchanges WHERE id = %s
                      )
                      AND status = 'active'
                    """,
                    (learner_id, exchange_id),
                )

                learner_tx_id = db.execute(
                    """
                    INSERT INTO credit_transactions
                        (user_id, amount_delta, entry_type, description, skill_id, exchange_id)
                    VALUES (%s, %s, 'deduction', %s, %s, %s)
                    """,
                    (learner_id, -amount, deduction, listing_id, exchange_id),
                )
                db.execute(
                    """
                    UPDATE users
                    SET credit_balance = credit_balance - %s
                    WHERE id = %s
                    """,
                    (amount, learner_id),
                )

                teacher_tx_id = db.execute(
                    """
                    INSERT INTO credit_transactions
                        (user_id, amount_delta, entry_type, description, skill_id, exchange_id)
                    VALUES (%s, %s, 'earning', %s, %s, %s)
                    """,
                    (teacher_id, amount, earning, listing_id, exchange_id),
                )
                db.execute(
                    """
                    UPDATE users
                    SET credit_balance = credit_balance + %s
                    WHERE id = %s
                    """,
                    (amount, teacher_id),
                )

                db.execute(
                    """
                    UPDATE profiles
                    SET completed_exchange_count = completed_exchange_count + 1
                    WHERE user_id IN (%s, %s)
                    """,
                    (learner_id, teacher_id),
                )

                learner_row = db.fetch_one(
                    "SELECT * FROM credit_transactions WHERE id = %s", (learner_tx_id,)
                )
                teacher_row = db.fetch_one(
                    "SELECT * FROM credit_transactions WHERE id = %s", (teacher_tx_id,)
                )
        return (CreditTransaction.from_row(learner_row), CreditTransaction.from_row(teacher_row))

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
