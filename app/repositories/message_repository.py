from __future__ import annotations

from types import SimpleNamespace

from app.models.message import MessageConversation, MessagePost

from .base_repository import BaseRepository


class MessageRepository(BaseRepository):
    def create_conversation(
        self,
        *,
        subject: str,
        permission_source: str,
        participant_ids: list[int],
    ) -> MessageConversation:
        with self._db() as db:
            with db.transaction():
                conversation_id = db.execute(
                    """
                    INSERT INTO message_conversations (subject, permission_source)
                    VALUES (%s, %s)
                    """,
                    (subject, permission_source),
                )
                db.execute_many(
                    """
                    INSERT INTO message_participants (conversation_id, user_id)
                    VALUES (%s, %s)
                    """,
                    [(conversation_id, user_id) for user_id in participant_ids],
                )
        conversation = self.find_for_user(conversation_id, participant_ids[0])
        if conversation is None:
            raise RuntimeError("Conversation was not created correctly.")
        return conversation

    def list_for_user(self, user_id: int) -> list[MessageConversation]:
        with self._db() as db:
            rows = db.fetch_all(
                """
                SELECT c.*
                FROM message_conversations c
                JOIN message_participants p ON p.conversation_id = c.id
                WHERE p.user_id = %s
                ORDER BY c.updated_at DESC, c.id DESC
                """,
                (user_id,),
            )
        conversations = [item for row in rows if (item := MessageConversation.from_row(row))]
        for conversation in conversations:
            self._hydrate_summary(conversation, user_id)
        return conversations

    def find_for_user(self, conversation_id: int, user_id: int) -> MessageConversation | None:
        with self._db() as db:
            row = db.fetch_one(
                """
                SELECT c.*
                FROM message_conversations c
                JOIN message_participants p ON p.conversation_id = c.id
                WHERE c.id = %s AND p.user_id = %s
                """,
                (conversation_id, user_id),
            )
        conversation = MessageConversation.from_row(row)
        if conversation:
            self._hydrate_summary(conversation, user_id)
        return conversation

    def find_between_users(self, user_a_id: int, user_b_id: int) -> MessageConversation | None:
        with self._db() as db:
            row = db.fetch_one(
                """
                SELECT c.*
                FROM message_conversations c
                JOIN message_participants pa ON pa.conversation_id = c.id AND pa.user_id = %s
                JOIN message_participants pb ON pb.conversation_id = c.id AND pb.user_id = %s
                ORDER BY c.updated_at DESC, c.id DESC
                LIMIT 1
                """,
                (user_a_id, user_b_id),
            )
        return MessageConversation.from_row(row)

    def list_messages(self, conversation_id: int) -> list[MessagePost]:
        with self._db() as db:
            rows = db.fetch_all(
                """
                SELECT m.*, u.full_name AS sender_name
                FROM message_posts m
                JOIN users u ON u.id = m.sender_id
                WHERE m.conversation_id = %s
                ORDER BY m.created_at ASC, m.id ASC
                """,
                (conversation_id,),
            )
        return [item for row in rows if (item := MessagePost.from_row(row))]

    def create_message(self, *, conversation_id: int, sender_id: int, body: str) -> MessagePost:
        with self._db() as db:
            with db.transaction():
                message_id = db.execute(
                    """
                    INSERT INTO message_posts (conversation_id, sender_id, body)
                    VALUES (%s, %s, %s)
                    """,
                    (conversation_id, sender_id, body),
                )
                db.execute(
                    "UPDATE message_conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (conversation_id,),
                )
                row = db.fetch_one(
                    """
                    SELECT m.*, u.full_name AS sender_name
                    FROM message_posts m
                    JOIN users u ON u.id = m.sender_id
                    WHERE m.id = %s
                    """,
                    (message_id,),
                )
        message = MessagePost.from_row(row)
        if message is None:
            raise RuntimeError("Message was not created correctly.")
        return message

    def mark_read(self, *, conversation_id: int, user_id: int) -> None:
        with self._db() as db:
            with db.transaction():
                db.execute(
                    """
                    UPDATE message_posts
                    SET read_at = CURRENT_TIMESTAMP
                    WHERE conversation_id = %s
                      AND sender_id <> %s
                      AND read_at IS NULL
                    """,
                    (conversation_id, user_id),
                )
                db.execute(
                    """
                    UPDATE message_participants
                    SET last_read_at = CURRENT_TIMESTAMP
                    WHERE conversation_id = %s AND user_id = %s
                    """,
                    (conversation_id, user_id),
                )

    def is_participant(self, conversation_id: int, user_id: int) -> bool:
        with self._db() as db:
            row = db.fetch_one(
                """
                SELECT 1
                FROM message_participants
                WHERE conversation_id = %s AND user_id = %s
                """,
                (conversation_id, user_id),
            )
        return row is not None

    def count_unread(self, user_id: int) -> int:
        with self._db() as db:
            row = db.fetch_one(
                """
                SELECT COUNT(*) AS count
                FROM message_posts m
                JOIN message_participants p ON p.conversation_id = m.conversation_id
                WHERE p.user_id = %s
                  AND m.sender_id <> %s
                  AND m.read_at IS NULL
                """,
                (user_id, user_id),
            )
        return int((row or {}).get("count") or 0)

    def _hydrate_summary(self, conversation: MessageConversation, current_user_id: int) -> None:
        with self._db() as db:
            participants = db.fetch_all(
                """
                SELECT u.id, u.full_name, u.email
                FROM message_participants p
                JOIN users u ON u.id = p.user_id
                WHERE p.conversation_id = %s
                ORDER BY u.full_name ASC
                """,
                (conversation.id,),
            )
            last_row = db.fetch_one(
                """
                SELECT m.*, u.full_name AS sender_name
                FROM message_posts m
                JOIN users u ON u.id = m.sender_id
                WHERE m.conversation_id = %s
                ORDER BY m.created_at DESC, m.id DESC
                LIMIT 1
                """,
                (conversation.id,),
            )
            unread_row = db.fetch_one(
                """
                SELECT COUNT(*) AS count
                FROM message_posts
                WHERE conversation_id = %s
                  AND sender_id <> %s
                  AND read_at IS NULL
                """,
                (conversation.id, current_user_id),
            )
        conversation.participants = [
            SimpleNamespace(id=row["id"], full_name=row["full_name"], email=row["email"])
            for row in participants
        ]
        conversation.last_message = MessagePost.from_row(last_row)
        conversation.unread_count = int((unread_row or {}).get("count") or 0)

    def list_messages_since(self, conversation_id: int, last_id: int) -> list[MessagePost]:
        with self._db() as db:
            rows = db.fetch_all(
                """
                SELECT m.*, u.full_name AS sender_name
                FROM message_posts m
                JOIN users u ON u.id = m.sender_id
                WHERE m.conversation_id = %s AND m.id > %s
                ORDER BY m.created_at ASC, m.id ASC
                """,
                (conversation_id, last_id),
            )
        return [item for row in rows if (item := MessagePost.from_row(row))]
