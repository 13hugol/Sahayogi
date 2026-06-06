from __future__ import annotations

from app.models.message import MessageConversation, MessagePost
from app.repositories.message_repository import MessageRepository


class MessageService:
    ALLOWED_PERMISSION_SOURCES = {"accepted_exchange", "match"}
    MAX_BODY_LENGTH = 2000

    def __init__(self, message_repository: MessageRepository):
        self._message_repository = message_repository

    def create_conversation(
        self,
        *,
        subject: str,
        permission_source: str,
        participant_ids: list[int],
    ) -> MessageConversation:
        if permission_source not in self.ALLOWED_PERMISSION_SOURCES:
            raise ValueError("Messages require an accepted exchange or mutual match.")
        unique_participants = list(dict.fromkeys(participant_ids))
        if len(unique_participants) != 2:
            raise ValueError("A messaging conversation requires exactly two participants.")
        cleaned_subject = " ".join(subject.split())
        if not cleaned_subject:
            raise ValueError("Conversation subject is required.")
        return self._message_repository.create_conversation(
            subject=cleaned_subject[:160],
            permission_source=permission_source,
            participant_ids=unique_participants,
        )

    def list_conversations(self, user_id: int) -> list[MessageConversation]:
        return self._message_repository.list_for_user(user_id)

    def get_conversation(self, conversation_id: int, user_id: int) -> MessageConversation | None:
        conversation = self._message_repository.find_for_user(conversation_id, user_id)
        if not conversation:
            return None
        conversation.messages = self._message_repository.list_messages(conversation_id)
        return conversation

    def send_message(self, *, conversation_id: int, sender_id: int, body: str) -> MessagePost:
        if not self._message_repository.is_participant(conversation_id, sender_id):
            raise PermissionError("You do not have access to this conversation.")
        cleaned_body = body.strip()
        if not cleaned_body:
            raise ValueError("Message cannot be empty.")
        if len(cleaned_body) > self.MAX_BODY_LENGTH:
            raise ValueError("Message must be 2000 characters or fewer.")
        return self._message_repository.create_message(
            conversation_id=conversation_id,
            sender_id=sender_id,
            body=cleaned_body,
        )

    def mark_read(self, *, conversation_id: int, user_id: int) -> None:
        if self._message_repository.is_participant(conversation_id, user_id):
            self._message_repository.mark_read(conversation_id=conversation_id, user_id=user_id)

    def count_unread(self, user_id: int) -> int:
        return self._message_repository.count_unread(user_id)
