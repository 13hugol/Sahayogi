from __future__ import annotations

from app.repositories import NotificationRepository


class NotificationService:
    EVENT_NEW_MATCH = "new_match"
    EVENT_EXCHANGE_REQUEST = "exchange_request"
    EVENT_REQUEST_ACCEPTED = "request_accepted"
    EVENT_REQUEST_DECLINED = "request_declined"
    EVENT_NEW_MESSAGE = "new_message"
    EVENT_NEW_REVIEW = "new_review"

    def __init__(self, notification_repository: NotificationRepository):
        self._notification_repository = notification_repository

    def list_for_user(self, user_id: int, *, limit: int = 20):
        return self._notification_repository.for_user(user_id, limit=limit)

    def unread_count(self, user_id: int) -> int:
        return self._notification_repository.unread_count(user_id)

    def mark_all_read(self, user_id: int) -> int:
        return self._notification_repository.mark_all_read(user_id)

    def mark_read(self, user_id: int, notification_id: int):
        return self._notification_repository.mark_read(notification_id, user_id)

    def create_notification(
        self,
        *,
        user_id: int,
        event_type: str,
        title: str,
        body: str,
        target_url: str | None = None,
    ):
        return self._notification_repository.create(
            user_id=user_id,
            event_type=event_type,
            title=title,
            body=body,
            target_url=target_url,
        )

    def notify_new_match(self, *, user_id: int, member_name: str, target_url: str | None = "/matches/"):
        return self.create_notification(
            user_id=user_id,
            event_type=self.EVENT_NEW_MATCH,
            title="New mutual match",
            body=f"You have a new mutual skill match with {member_name}.",
            target_url=target_url,
        )

    def notify_exchange_request(self, *, user_id: int, requester_name: str, skill_title: str, target_url: str):
        return self.create_notification(
            user_id=user_id,
            event_type=self.EVENT_EXCHANGE_REQUEST,
            title="New exchange request",
            body=f"{requester_name} requested {skill_title}.",
            target_url=target_url,
        )

    def notify_request_accepted(self, *, user_id: int, skill_title: str, target_url: str):
        return self.create_notification(
            user_id=user_id,
            event_type=self.EVENT_REQUEST_ACCEPTED,
            title="Request accepted",
            body=f"Your request for {skill_title} was accepted.",
            target_url=target_url,
        )

    def notify_request_declined(self, *, user_id: int, skill_title: str, target_url: str):
        return self.create_notification(
            user_id=user_id,
            event_type=self.EVENT_REQUEST_DECLINED,
            title="Request declined",
            body=f"Your request for {skill_title} was declined.",
            target_url=target_url,
        )

    def notify_new_message(self, *, user_id: int, sender_name: str, conversation_id: int):
        return self.create_notification(
            user_id=user_id,
            event_type=self.EVENT_NEW_MESSAGE,
            title="New message",
            body=f"{sender_name} sent you a new message.",
            target_url=f"/messages/{conversation_id}",
        )

    def notify_new_review(self, *, user_id: int, reviewer_name: str, target_url: str):
        return self.create_notification(
            user_id=user_id,
            event_type=self.EVENT_NEW_REVIEW,
            title="New review",
            body=f"{reviewer_name} left you a review.",
            target_url=target_url,
        )
