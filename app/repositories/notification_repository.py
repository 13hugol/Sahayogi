from __future__ import annotations

from app.models import Notification

from .base_repository import BaseRepository


class NotificationRepository(BaseRepository):
    def create(
        self,
        *,
        user_id: int,
        event_type: str,
        title: str,
        body: str,
        target_url: str | None = None,
    ) -> Notification:
        with self._db() as db:
            notification_id = db.execute(
                """
                INSERT INTO notifications (user_id, event_type, title, body, target_url)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (user_id, event_type, title, body, target_url),
            )
            row = db.fetch_one("SELECT * FROM notifications WHERE id = %s", (notification_id,))
        return Notification.from_row(row)

    def for_user(self, user_id: int, *, limit: int = 20) -> list[Notification]:
        with self._db() as db:
            rows = db.fetch_all(
                """
                SELECT *
                FROM notifications
                WHERE user_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
        return [notification for row in rows if (notification := Notification.from_row(row))]

    def unread_count(self, user_id: int) -> int:
        with self._db() as db:
            row = db.fetch_one(
                """
                SELECT COUNT(*) AS count
                FROM notifications
                WHERE user_id = %s AND is_read = FALSE
                """,
                (user_id,),
            )
        return int((row or {}).get("count") or 0)

    def find_for_user(self, notification_id: int, user_id: int) -> Notification | None:
        with self._db() as db:
            row = db.fetch_one(
                """
                SELECT *
                FROM notifications
                WHERE id = %s AND user_id = %s
                """,
                (notification_id, user_id),
            )
        return Notification.from_row(row)

    def mark_read(self, notification_id: int, user_id: int) -> Notification | None:
        with self._db() as db:
            db.execute(
                """
                UPDATE notifications
                SET is_read = TRUE, read_at = COALESCE(read_at, CURRENT_TIMESTAMP)
                WHERE id = %s AND user_id = %s
                """,
                (notification_id, user_id),
            )
            row = db.fetch_one(
                "SELECT * FROM notifications WHERE id = %s AND user_id = %s",
                (notification_id, user_id),
            )
        return Notification.from_row(row)

    def mark_all_read(self, user_id: int) -> int:
        with self._db() as db:
            row = db.fetch_one(
                """
                SELECT COUNT(*) AS count
                FROM notifications
                WHERE user_id = %s AND is_read = FALSE
                """,
                (user_id,),
            )
            db.execute(
                """
                UPDATE notifications
                SET is_read = TRUE, read_at = COALESCE(read_at, CURRENT_TIMESTAMP)
                WHERE user_id = %s AND is_read = FALSE
                """,
                (user_id,),
            )
        return int((row or {}).get("count") or 0)
