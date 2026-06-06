from __future__ import annotations

import re

from app.models.notification import Notification

from .base_repository import BaseRepository


_TARGET_ID_RE = re.compile(r"#match-(\d+)")


class NotificationRepository(BaseRepository):
    def create(
        self,
        user_id: int,
        message: str | None = None,
        event_type: str | None = None,
        *,
        title: str | None = None,
        body: str | None = None,
        target_url: str | None = None,
    ) -> int:
        text = body or message or ""
        title_text = title or text[:80] or "Notification"
        event = event_type or "general"
        with self._db() as db:
            notification_id = db.execute(
                """
                INSERT INTO notifications
                    (user_id, event_type, title, body, message, target_url, is_read)
                VALUES (%s, %s, %s, %s, %s, %s, FALSE)
                """,
                (user_id, event, title_text, text, text, target_url),
            )
        return int(notification_id)

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

    def get_unread_count(self, user_id: int) -> int:
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

    def get_unread_notifications(self, user_id: int) -> list[Notification]:
        with self._db() as db:
            rows = db.fetch_all(
                """
                SELECT *
                FROM notifications
                WHERE user_id = %s AND is_read = FALSE
                ORDER BY created_at DESC, id DESC
                """,
                (user_id,),
            )
        return [notification for row in rows if (notification := Notification.from_row(row))]

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
                SET is_read = TRUE,
                    read_at = COALESCE(read_at, CURRENT_TIMESTAMP)
                WHERE id = %s AND user_id = %s
                """,
                (notification_id, user_id),
            )
            row = db.fetch_one(
                "SELECT * FROM notifications WHERE id = %s AND user_id = %s",
                (notification_id, user_id),
            )
        return Notification.from_row(row)

    def mark_all_as_read(self, user_id: int) -> int:
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
                SET is_read = TRUE,
                    read_at = COALESCE(read_at, CURRENT_TIMESTAMP)
                WHERE user_id = %s AND is_read = FALSE
                """,
                (user_id,),
            )
        return int((row or {}).get("count") or 0)

    def mark_all_read(self, user_id: int) -> int:
        return self.mark_all_as_read(user_id)

    def get_notified_match_ids(self, user_id: int) -> list[int]:
        with self._db() as db:
            rows = db.fetch_all(
                """
                SELECT target_url
                FROM notifications
                WHERE user_id = %s AND event_type = 'new_match'
                """,
                (user_id,),
            )
        ids: set[int] = set()
        for row in rows:
            target = row.get("target_url") or ""
            match = _TARGET_ID_RE.search(target)
            if match:
                try:
                    ids.add(int(match.group(1)))
                except (TypeError, ValueError):
                    continue
        return sorted(ids)
