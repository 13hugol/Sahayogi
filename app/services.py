from __future__ import annotations

import math
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from uuid import uuid4

from flask import current_app, url_for
from flask_login import current_user
from itsdangerous import URLSafeTimedSerializer
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from .extensions import db
from .models import (
    AccountDeletionRequest,
    AdminAuditLog,
    Conversation,
    CreditHold,
    CreditLedger,
    Exchange,
    ExchangeCompletion,
    Match,
    Message,
    MessageRead,
    Notification,
    Review,
    Skill,
    User,
    UserSkillOffer,
    UserSkillWant,
    refresh_profile_metrics,
    utcnow,
)


def serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def generate_token(email: str, purpose: str) -> str:
    return serializer().dumps({"email": email, "purpose": purpose})


def validate_token(token: str, purpose: str, max_age: int) -> str | None:
    try:
        payload = serializer().loads(token, max_age=max_age)
    except Exception:
        return None
    if payload.get("purpose") != purpose:
        return None
    return payload.get("email")


def send_email(subject: str, recipient: str, body: str) -> None:
    mail_server = current_app.config.get("MAIL_SERVER")
    sender = current_app.config["MAIL_DEFAULT_SENDER"]
    if not mail_server:
        log_file = Path(current_app.config["MAIL_LOG_FILE"])
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(f"TO: {recipient}\nSUBJECT: {subject}\n{body}\n{'-' * 60}\n")
        current_app.logger.info("Email captured in %s for %s", log_file, recipient)
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content(body)
    port = current_app.config["MAIL_PORT"]
    if current_app.config["MAIL_USE_TLS"]:
        with smtplib.SMTP(mail_server, port) as client:
            client.starttls()
            if current_app.config["MAIL_USERNAME"]:
                client.login(
                    current_app.config["MAIL_USERNAME"],
                    current_app.config["MAIL_PASSWORD"],
                )
            client.send_message(message)
    else:
        with smtplib.SMTP(mail_server, port) as client:
            if current_app.config["MAIL_USERNAME"]:
                client.login(
                    current_app.config["MAIL_USERNAME"],
                    current_app.config["MAIL_PASSWORD"],
                )
            client.send_message(message)


def build_absolute_url(endpoint: str, **values) -> str:
    return url_for(endpoint, _external=True, **values)


def create_notification(user: User, title: str, body: str, url: str | None = None, kind: str = "info") -> Notification:
    notification = Notification(user=user, title=title, body=body, url=url, kind=kind)
    db.session.add(notification)
    return notification


def audit(action: str, target_type: str, target_id: int | None = None, detail: str | None = None) -> None:
    if not current_user.is_authenticated:
        return
    db.session.add(
        AdminAuditLog(
            admin_id=current_user.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )
    )


def save_upload(
    uploaded_file: FileStorage,
    subfolder: str,
    allowed_extensions: set[str],
) -> str:
    suffix = Path(uploaded_file.filename or "").suffix.lower().lstrip(".")
    if suffix not in allowed_extensions:
        raise ValueError("Unsupported file type.")
    upload_root = Path(current_app.config["UPLOAD_FOLDER"]) / subfolder
    upload_root.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(uploaded_file.filename or "upload")
    filename = f"{uuid4().hex}-{safe_name}"
    destination = upload_root / filename
    uploaded_file.save(destination)
    return str(destination.relative_to(Path(current_app.config["UPLOAD_FOLDER"])))


def normalize_account_status(user: User) -> None:
    if user.status == "suspended" and user.suspended_until and user.suspended_until <= utcnow():
        user.status = "active"
        user.suspended_until = None
        db.session.commit()


def register_failed_login(user: User) -> None:
    now = utcnow()
    window_minutes = current_app.config["LOCKOUT_WINDOW_MINUTES"]
    if not user.failed_login_window_started_at or user.failed_login_window_started_at < now - timedelta(
        minutes=window_minutes
    ):
        user.failed_login_window_started_at = now
        user.failed_login_count = 1
    else:
        user.failed_login_count += 1
    if user.failed_login_count >= current_app.config["LOCKOUT_THRESHOLD"]:
        user.locked_until = now + timedelta(minutes=current_app.config["LOCKOUT_DURATION_MINUTES"])
        user.failed_login_count = 0
        user.failed_login_window_started_at = None
    db.session.commit()


def clear_failed_logins(user: User) -> None:
    user.failed_login_count = 0
    user.failed_login_window_started_at = None
    user.locked_until = None
    user.last_login_at = utcnow()
    db.session.commit()


def append_ledger_entry(
    user: User,
    delta: int,
    entry_type: str,
    description: str,
    related_request_id: int | None = None,
    related_exchange_id: int | None = None,
) -> CreditLedger:
    balance_after = user.credit_balance + delta
    entry = CreditLedger(
        user=user,
        amount_delta=delta,
        balance_after=balance_after,
        entry_type=entry_type,
        description=description,
        related_request_id=related_request_id,
        related_exchange_id=related_exchange_id,
    )
    db.session.add(entry)
    return entry


def seed_initial_credits(user: User) -> None:
    append_ledger_entry(
        user,
        current_app.config["INITIAL_CREDITS"],
        "welcome",
        "Welcome credit allocation.",
    )


def reserve_credits(user: User, request_id: int, amount: int) -> CreditHold:
    if user.available_credit_balance < amount:
        raise ValueError("Insufficient credits.")
    hold = CreditHold(user=user, request_id=request_id, amount=amount, status="reserved")
    db.session.add(hold)
    return hold


def release_hold(hold: CreditHold | None) -> None:
    if not hold or hold.status != "reserved":
        return
    hold.status = "refunded"
    hold.released_at = utcnow()


def settle_hold(hold: CreditHold | None, exchange: Exchange) -> None:
    if not hold or hold.status != "reserved":
        return
    append_ledger_entry(
        exchange.learner,
        -hold.amount,
        "spend",
        f"Credits transferred for exchange #{exchange.id}.",
        related_request_id=exchange.request_id,
        related_exchange_id=exchange.id,
    )
    append_ledger_entry(
        exchange.teacher,
        hold.amount,
        "earn",
        f"Credits earned from exchange #{exchange.id}.",
        related_request_id=exchange.request_id,
        related_exchange_id=exchange.id,
    )
    hold.status = "settled"
    hold.released_at = utcnow()


def get_or_create_conversation(user_one_id: int, user_two_id: int, subject: str, exchange: Exchange | None = None) -> Conversation:
    first, second = sorted([user_one_id, user_two_id])
    query = Conversation.query.filter_by(user_one_id=first, user_two_id=second)
    if exchange:
        query = query.filter_by(exchange_id=exchange.id)
    conversation = query.first()
    if conversation:
        return conversation
    conversation = Conversation(
        exchange=exchange,
        user_one_id=first,
        user_two_id=second,
        subject=subject,
    )
    db.session.add(conversation)
    db.session.flush()
    return conversation


def mark_conversation_read(conversation: Conversation, user: User) -> None:
    unread_messages = conversation.messages.filter(
        Message.sender_id != user.id,
        ~Message.reads.any(MessageRead.user_id == user.id),
    )
    for message in unread_messages:
        db.session.add(MessageRead(message=message, user=user))


def can_access_conversation(conversation: Conversation, user_id: int) -> bool:
    return user_id in {conversation.user_one_id, conversation.user_two_id}


def recalculate_reputation(user: User) -> None:
    refresh_profile_metrics(user)


def complete_exchange(exchange: Exchange, user: User) -> bool:
    existing = next((mark for mark in exchange.completion_marks if mark.user_id == user.id), None)
    if existing:
        return False
    db.session.add(ExchangeCompletion(exchange=exchange, user=user))
    db.session.flush()
    if len(exchange.completion_marks) >= 2:
        exchange.status = "completed"
        exchange.completed_at = utcnow()
        if exchange.exchange_type == "credit":
            settle_hold(exchange.request.credit_hold, exchange)
        for participant in [exchange.teacher, exchange.learner]:
            create_notification(
                participant,
                "Exchange completed",
                f"Exchange #{exchange.id} is now marked complete.",
                url_for("exchanges.detail", exchange_id=exchange.id),
                "success",
            )
        recalculate_reputation(exchange.teacher)
        recalculate_reputation(exchange.learner)
    return True


def review_allowed(exchange: Exchange, reviewer_id: int) -> bool:
    if exchange.status != "completed":
        return False
    if reviewer_id not in {exchange.teacher_id, exchange.learner_id}:
        return False
    return exchange.reviews.filter_by(reviewer_id=reviewer_id).first() is None


def update_skill_links(user: User, offered_skill_ids: list[int], wanted_skill_ids: list[int]) -> None:
    user.offered_skills[:] = [
        UserSkillOffer(user=user, skill_id=skill_id) for skill_id in sorted(set(offered_skill_ids))
    ]
    user.wanted_skills[:] = [
        UserSkillWant(user=user, skill_id=skill_id) for skill_id in sorted(set(wanted_skill_ids))
    ]


def unique_username(base: str) -> str:
    candidate = "".join(ch.lower() for ch in base if ch.isalnum())[:20] or "member"
    username = candidate
    counter = 1
    from .models import Profile

    with db.session.no_autoflush:
        while Profile.query.filter_by(username=username).first():
            counter += 1
            username = f"{candidate}{counter}"
    return username


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def build_matches_for_user(user: User) -> list[dict]:
    offered_ids = {row.skill_id for row in user.offered_skills}
    wanted_ids = {row.skill_id for row in user.wanted_skills}
    if not offered_ids and not wanted_ids:
        return []

    matches: list[dict] = []
    for candidate in User.query.filter(User.id != user.id, User.deleted_at.is_(None)).all():
        candidate_offered = {row.skill_id for row in candidate.offered_skills}
        candidate_wanted = {row.skill_id for row in candidate.wanted_skills}
        overlap_teach = offered_ids.intersection(candidate_wanted)
        overlap_learn = wanted_ids.intersection(candidate_offered)
        if not overlap_teach and not overlap_learn:
            continue
        teach_names = [
            skill.name for skill in Skill.query.filter(Skill.id.in_(overlap_teach)).order_by(Skill.name).all()
        ]
        learn_names = [
            skill.name for skill in Skill.query.filter(Skill.id.in_(overlap_learn)).order_by(Skill.name).all()
        ]
        summary_parts = []
        if teach_names:
            summary_parts.append(f"You can teach: {', '.join(teach_names)}")
        if learn_names:
            summary_parts.append(f"You can learn: {', '.join(learn_names)}")
        Match.query.filter_by(seeker_id=user.id, partner_id=candidate.id).delete()
        db.session.add(
            Match(
                seeker_id=user.id,
                partner_id=candidate.id,
                overlap_summary=" | ".join(summary_parts),
            )
        )
        matches.append(
            {
                "user": candidate,
                "teach_names": teach_names,
                "learn_names": learn_names,
                "summary": " | ".join(summary_parts),
            }
        )
    db.session.flush()
    return matches


def unread_counts_for(user: User) -> dict[str, int]:
    notification_count = user.notifications.filter_by(is_read=False).count()
    message_count = sum(
        1
        for conversation in Conversation.query.filter(
            (Conversation.user_one_id == user.id) | (Conversation.user_two_id == user.id)
        ).all()
        for message in conversation.messages
        if message.sender_id != user.id and not any(read.user_id == user.id for read in message.reads)
    )
    return {"notifications": notification_count, "messages": message_count}


def schedule_account_deletion(user: User) -> AccountDeletionRequest:
    scheduled_purge = utcnow() + timedelta(days=current_app.config["ACCOUNT_DELETE_GRACE_DAYS"])
    user.deleted_at = utcnow()
    user.scheduled_purge_at = scheduled_purge
    user.status = "deleted"
    deletion_request = AccountDeletionRequest(
        user=user,
        status="pending",
        scheduled_purge_at=scheduled_purge,
    )
    db.session.add(deletion_request)
    return deletion_request


def purge_due_accounts() -> int:
    purged = 0
    now = utcnow()
    due_requests = AccountDeletionRequest.query.filter(
        AccountDeletionRequest.status == "pending",
        AccountDeletionRequest.scheduled_purge_at <= now,
    ).all()
    for request in due_requests:
        request.status = "processed"
        request.processed_at = now
        db.session.delete(request.user)
        purged += 1
    return purged
