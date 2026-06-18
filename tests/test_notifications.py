from __future__ import annotations

from datetime import datetime

from app.models import Notification
from app.services import NotificationService


def test_notification_service_generates_required_event_types():
    repository = FakeNotificationRepository()
    service = NotificationService(repository)

    service.notify_new_match(user_id=1, member_name="Maya")
    service.notify_exchange_request(
        user_id=1,
        requester_name="Aarav",
        skill_title="Python web basics",
        target_url="/requests/inbox",
    )
    service.notify_request_accepted(user_id=1, skill_title="Guitar lessons", target_url="/requests/sent")
    service.notify_request_declined(user_id=1, skill_title="Kitchen basics", target_url="/requests/sent")
    service.notify_new_message(user_id=1, sender_name="Sita", conversation_id=7)
    service.notify_new_review(user_id=1, reviewer_name="Hari", target_url="/reviews/users/1")

    event_types = [notification.event_type for notification in repository.notifications]

    assert event_types == [
        "new_match",
        "exchange_request",
        "request_accepted",
        "request_declined",
        "new_message",
        "new_review",
    ]
    assert repository.notifications[4].title == "New message"
    assert repository.notifications[4].target_url == "/messages/7"


def test_notification_counts_and_mark_read_actions():
    repository = FakeNotificationRepository()
    service = NotificationService(repository)
    first = service.notify_new_match(user_id=3, member_name="Mina")
    service.notify_new_review(user_id=3, reviewer_name="Pema", target_url="/reviews/users/3")

    assert service.unread_count(3) == 2

    opened = service.mark_read(user_id=3, notification_id=first.id)

    assert opened.is_read is True
    assert service.unread_count(3) == 1

    updated = service.mark_all_read(3)

    assert updated == 1
    assert service.unread_count(3) == 0


def test_notification_list_is_user_scoped():
    repository = FakeNotificationRepository()
    service = NotificationService(repository)
    service.notify_new_match(user_id=4, member_name="Only This User")
    service.notify_new_match(user_id=5, member_name="Other User")

    notifications = service.list_for_user(4)

    assert len(notifications) == 1
    assert notifications[0].body == "You have a new mutual skill match with Only This User."


class FakeNotificationRepository:
    def __init__(self):
        self.notifications = []
        self.next_id = 1

    def create(self, *, user_id, event_type, title, body, target_url=None):
        notification = Notification(
            id=self.next_id,
            user_id=user_id,
            event_type=event_type,
            title=title,
            body=body,
            target_url=target_url,
            is_read=False,
            created_at=datetime(2026, 6, 2, 9, 0, 0),
        )
        self.next_id += 1
        self.notifications.append(notification)
        return notification

    def for_user(self, user_id, *, limit=20):
        rows = [notification for notification in self.notifications if notification.user_id == user_id]
        return rows[:limit]

    def unread_count(self, user_id):
        return len(
            [
                notification
                for notification in self.notifications
                if notification.user_id == user_id and not notification.is_read
            ]
        )

    def get_unread_count(self, user_id):
        return self.unread_count(user_id)

    def mark_read(self, notification_id, user_id):
        for notification in self.notifications:
            if notification.id == notification_id and notification.user_id == user_id:
                notification.is_read = True
                return notification
        return None

    def mark_all_read(self, user_id):
        unread = [
            notification
            for notification in self.notifications
            if notification.user_id == user_id and not notification.is_read
        ]
        for notification in unread:
            notification.is_read = True
        return len(unread)
