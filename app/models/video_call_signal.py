from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models.base_model import BaseModel


@dataclass
class VideoCallSignal(BaseModel):
    """A single WebRTC signaling message exchanged between two call participants.

    Signaling is stored in MySQL and polled by each participant: offer, answer,
    ICE candidates, and a `leave` notice when a peer ends the call.
    """

    id: int
    exchange_id: int
    sender_id: int
    recipient_id: int
    signal_type: str
    payload: str
    consumed_at: datetime | None = None
    created_at: datetime | None = None

    @classmethod
    def from_row(cls, row: dict | None) -> VideoCallSignal | None:
        if not row:
            return None
        return cls(
            id=row["id"],
            exchange_id=row["exchange_id"],
            sender_id=row["sender_id"],
            recipient_id=row["recipient_id"],
            signal_type=row["signal_type"],
            payload=row["payload"] if row["payload"] is not None else "",
            consumed_at=row.get("consumed_at"),
            created_at=row.get("created_at"),
        )
