from __future__ import annotations

from app.models.video_call_signal import VideoCallSignal
from .base_repository import BaseRepository


class VideoCallSignalRepository(BaseRepository):
    """Stores and retrieves WebRTC signaling messages for in-app video calls.

    Each signal is addressed from one participant to the other. A participant
    polls for unconsumed signals addressed to them; fetching marks them consumed
    so they are not replayed on the next poll.
    """

    VALID_TYPES = {"offer", "answer", "ice", "leave"}

    def add_signal(
        self,
        *,
        exchange_id: int,
        sender_id: int,
        recipient_id: int,
        signal_type: str,
        payload: str,
    ) -> VideoCallSignal:
        with self._db() as db:
            signal_id = db.execute(
                """
                INSERT INTO video_call_signals
                    (exchange_id, sender_id, recipient_id, signal_type, payload)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (exchange_id, sender_id, recipient_id, signal_type, payload),
            )
            row = db.fetch_one("SELECT * FROM video_call_signals WHERE id = %s", (signal_id,))
        return VideoCallSignal.from_row(row)

    def consume_pending_for(self, *, exchange_id: int, recipient_id: int) -> list[VideoCallSignal]:
        """Return and mark-as-consumed all unconsumed signals for a participant."""
        with self._db() as db:
            rows = db.fetch_all(
                """
                SELECT * FROM video_call_signals
                WHERE exchange_id = %s AND recipient_id = %s AND consumed_at IS NULL
                ORDER BY created_at ASC
                """,
                (exchange_id, recipient_id),
            )
            if rows:
                ids = tuple(int(r["id"]) for r in rows)
                placeholders = ",".join(["%s"] * len(ids))
                db.execute(
                    f"""
                    UPDATE video_call_signals
                    SET consumed_at = CURRENT_TIMESTAMP
                    WHERE id IN ({placeholders})
                    """,
                    ids,
                )
        return [VideoCallSignal.from_row(row) for row in rows if row]

    def clear_for_exchange(self, exchange_id: int) -> None:
        """Remove pending signals when a call ends so stale offers do not linger."""
        with self._db() as db:
            db.execute(
                "DELETE FROM video_call_signals WHERE exchange_id = %s",
                (exchange_id,),
            )
