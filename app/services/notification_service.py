from __future__ import annotations

from app.repositories import NotificationRepository


class NotificationService:
    EVENT_NEW_MATCH = "new_match"
    EVENT_EXCHANGE_REQUEST = "exchange_request"
    EVENT_REQUEST_ACCEPTED = "request_accepted"
    EVENT_REQUEST_DECLINED = "request_declined"
    EVENT_NEW_MESSAGE = "new_message"
    EVENT_NEW_REVIEW = "new_review"
    EVENT_REPORT_RECEIVED = "report_received"
    EVENT_LISTING_APPROVED = "listing_approved"
    EVENT_LISTING_REJECTED = "listing_rejected"
    EVENT_GENERAL = "general"

    def __init__(self, notification_repository: NotificationRepository | None = None):
        self._notification_repository = notification_repository or NotificationRepository()

    def list_for_user(self, user_id: int, *, limit: int = 20):
        return self._notification_repository.for_user(user_id, limit=limit)

    def unread_count(self, user_id: int) -> int:
        return self._notification_repository.get_unread_count(user_id)

    def mark_all_read(self, user_id: int) -> int:
        return self._notification_repository.mark_all_read(user_id)

    def mark_read(self, user_id: int, notification_id: int):
        return self._notification_repository.mark_read(notification_id, user_id)

    def find(self, user_id: int, notification_id: int):
        return self._notification_repository.find_for_user(notification_id, user_id)

    def create_notification(
        self,
        *,
        user_id: int,
        event_type: str = EVENT_GENERAL,
        title: str,
        body: str,
        target_url: str | None = None,
    ) -> int:
        return self._notification_repository.create(
            user_id=user_id,
            event_type=event_type,
            title=title,
            body=body,
            target_url=target_url,
        )

    def notify_new_match(
        self,
        *,
        user_id: int,
        member_name: str,
        target_url: str | None = "/matches/",
    ) -> int:
        return self.create_notification(
            user_id=user_id,
            event_type=self.EVENT_NEW_MATCH,
            title="New mutual match",
            body=f"You have a new mutual skill match with {member_name}.",
            target_url=target_url,
        )

    def notify_exchange_request(
        self,
        *,
        user_id: int,
        requester_name: str,
        skill_title: str,
        target_url: str,
    ) -> int:
        return self.create_notification(
            user_id=user_id,
            event_type=self.EVENT_EXCHANGE_REQUEST,
            title="New exchange request",
            body=f"{requester_name} requested {skill_title}.",
            target_url=target_url,
        )

    def notify_request_accepted(
        self,
        *,
        user_id: int,
        skill_title: str,
        target_url: str,
    ) -> int:
        return self.create_notification(
            user_id=user_id,
            event_type=self.EVENT_REQUEST_ACCEPTED,
            title="Request accepted",
            body=f"Your request for {skill_title} was accepted.",
            target_url=target_url,
        )

    def notify_request_declined(
        self,
        *,
        user_id: int,
        skill_title: str,
        reason: str | None = None,
        target_url: str = "/requests/inbox",
    ) -> int:
        body = f"Your request for {skill_title} was declined."
        if reason:
            body += f" Reason: {reason}"
        return self.create_notification(
            user_id=user_id,
            event_type=self.EVENT_REQUEST_DECLINED,
            title="Request declined",
            body=body,
            target_url=target_url,
        )

    def notify_new_message(
        self,
        *,
        user_id: int,
        sender_name: str,
        conversation_id: int,
    ) -> int:
        return self.create_notification(
            user_id=user_id,
            event_type=self.EVENT_NEW_MESSAGE,
            title="New message",
            body=f"{sender_name} sent you a new message.",
            target_url=f"/messages/{conversation_id}",
        )

    def notify_new_review(
        self,
        *,
        user_id: int,
        reviewer_name: str,
        target_url: str = "/profile/me",
    ) -> int:
        return self.create_notification(
            user_id=user_id,
            event_type=self.EVENT_NEW_REVIEW,
            title="New review",
            body=f"{reviewer_name} left you a review.",
            target_url=target_url,
        )

    def notify_report_received(
        self,
        *,
        user_id: int,
        reported_name: str,
        target_url: str = "/profile/me",
    ) -> int:
        return self.create_notification(
            user_id=user_id,
            event_type=self.EVENT_REPORT_RECEIVED,
            title="Report submitted",
            body=f"Your report against {reported_name} has been received and is under review.",
            target_url=target_url,
        )

    def notify_listing_approved(
        self,
        *,
        user_id: int,
        skill_title: str,
        target_url: str = "/listings/mine",
    ) -> int:
        return self.create_notification(
            user_id=user_id,
            event_type=self.EVENT_LISTING_APPROVED,
            title="Listing approved",
            body=f"Your listing '{skill_title}' is now live.",
            target_url=target_url,
        )

    def notify_listing_rejected(
        self,
        *,
        user_id: int,
        skill_title: str,
        reason: str,
        target_url: str = "/listings/mine",
    ) -> int:
        return self.create_notification(
            user_id=user_id,
            event_type=self.EVENT_LISTING_REJECTED,
            title="Listing rejected",
            body=f"Your listing '{skill_title}' was rejected. Reason: {reason}",
            target_url=target_url,
        )
