from __future__ import annotations

from app.models.notification import Notification
from .base_repository import BaseRepository


class NotificationRepository(BaseRepository):
    def create(self, user_id: int, message: str) -> int:
        with self._db() as db:
            notification_id = db.execute(
                """
                INSERT INTO notifications (user_id, message, is_read)
                VALUES (%s, %s, FALSE)
                """,
                (user_id, message),
            )
        return notification_id

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
