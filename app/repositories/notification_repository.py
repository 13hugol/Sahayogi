from __future__ import annotations
from __future__ import annotations

from app.models.notification import Notification
from .base_repository import BaseRepository


class NotificationRepository(BaseRepository):
    def create(self, user_id: int, message: str, type: str = "general", target_url: str | None = None) -> int:
        with self._db() as db:
            notification_id = db.execute(
                """
                INSERT INTO notifications (user_id, message, is_read, type, target_url)
                VALUES (%s, %s, FALSE, %s, %s)
                """,
                (user_id, message, type, target_url),
            )
        return notification_id

    def message_exists(self, user_id: int, message: str) -> bool:
        with self._db() as db:
            row = db.fetch_one(
                """
                SELECT id
                FROM notifications
                WHERE user_id = %s AND message = %s
                LIMIT 1
                """,
                (user_id, message),
            )
        return row is not None

    def get_notified_match_ids(self, user_id: int) -> list[int]:
        with self._db() as db:
            rows = db.fetch_all(
                "SELECT target_url FROM notifications WHERE user_id = %s AND type = 'new_match'",
                (user_id,),
            )
        match_ids = []
        for row in rows:
            url = row.get("target_url")
            if url and "#match-" in url:
                try:
                    match_ids.append(int(url.split("#match-")[1]))
                except ValueError:
                    pass
        return match_ids

    def get_unread_count(self, user_id: int) -> int:
        with self._db() as db:
            row = db.fetch_one(
                "SELECT COUNT(*) AS count FROM notifications WHERE user_id = %s AND is_read = FALSE",
                (user_id,),
            )
        return int((row or {}).get("count") or 0)

    def get_unread_notifications(self, user_id: int) -> list[Notification]:
        with self._db() as db:
            rows = db.fetch_all(
                "SELECT * FROM notifications WHERE user_id = %s AND is_read = FALSE ORDER BY created_at DESC",
                (user_id,),
            )
        return [Notification.from_row(row) for row in rows if row]

    def mark_all_as_read(self, user_id: int) -> None:
        with self._db() as db:
            db.execute(
                "UPDATE notifications SET is_read = TRUE WHERE user_id = %s AND is_read = FALSE",
                (user_id,),
            )
