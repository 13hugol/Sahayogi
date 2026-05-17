from __future__ import annotations

from datetime import datetime
from statistics import mean

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, UniqueConstraint, func
from sqlalchemy.ext.hybrid import hybrid_property

from .extensions import bcrypt, db, login_manager


def utcnow() -> datetime:
    return datetime.utcnow()


class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False)
    description = db.Column(db.String(255))
    users = db.relationship("User", back_populates="role", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Role {self.name}>"


class User(UserMixin, db.Model):
    __table_args__ = (db.Index("ix_users_email", "email"),)

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_email_verified = db.Column(db.Boolean, default=True, nullable=False)
    status = db.Column(db.String(32), default="active", nullable=False)
    failed_login_count = db.Column(db.Integer, default=0, nullable=False)
    failed_login_window_started_at = db.Column(db.DateTime)
    locked_until = db.Column(db.DateTime)
    suspended_until = db.Column(db.DateTime)
    last_login_at = db.Column(db.DateTime)
    deleted_at = db.Column(db.DateTime)
    scheduled_purge_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )
    role_id = db.Column(db.Integer, db.ForeignKey("role.id"), nullable=False)

    role = db.relationship("Role", back_populates="users")
    profile = db.relationship("Profile", uselist=False, back_populates="user")
    offered_skills = db.relationship(
        "UserSkillOffer",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    wanted_skills = db.relationship(
        "UserSkillWant",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    listings = db.relationship(
        "Listing",
        back_populates="user",
        foreign_keys="Listing.user_id",
        lazy="dynamic",
    )
    certificates = db.relationship(
        "Certificate",
        back_populates="user",
        foreign_keys="Certificate.user_id",
        lazy="dynamic",
    )
    sent_requests = db.relationship(
        "ExchangeRequest",
        foreign_keys="ExchangeRequest.sender_id",
        back_populates="sender",
        lazy="dynamic",
    )
    received_requests = db.relationship(
        "ExchangeRequest",
        foreign_keys="ExchangeRequest.recipient_id",
        back_populates="recipient",
        lazy="dynamic",
    )
    taught_exchanges = db.relationship(
        "Exchange",
        foreign_keys="Exchange.teacher_id",
        back_populates="teacher",
        lazy="dynamic",
    )
    learned_exchanges = db.relationship(
        "Exchange",
        foreign_keys="Exchange.learner_id",
        back_populates="learner",
        lazy="dynamic",
    )
    sent_messages = db.relationship("Message", back_populates="sender", lazy="dynamic")
    notifications = db.relationship("Notification", back_populates="user", lazy="dynamic")
    reviews_written = db.relationship(
        "Review",
        foreign_keys="Review.reviewer_id",
        back_populates="reviewer",
        lazy="dynamic",
    )
    reviews_received = db.relationship(
        "Review",
        foreign_keys="Review.reviewee_id",
        back_populates="reviewee",
        lazy="dynamic",
    )
    reports_filed = db.relationship(
        "Report",
        foreign_keys="Report.reporter_id",
        back_populates="reporter",
        lazy="dynamic",
    )
    reports_against = db.relationship(
        "Report",
        foreign_keys="Report.reported_user_id",
        back_populates="reported_user",
        lazy="dynamic",
    )
    credit_entries = db.relationship("CreditLedger", back_populates="user", lazy="dynamic")
    credit_holds = db.relationship("CreditHold", back_populates="user", lazy="dynamic")
    deletion_requests = db.relationship(
        "AccountDeletionRequest",
        back_populates="user",
        lazy="dynamic",
    )

    def set_password(self, raw_password: str) -> None:
        self.password_hash = bcrypt.generate_password_hash(raw_password).decode("utf-8")

    def check_password(self, raw_password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, raw_password)

    @property
    def is_admin(self) -> bool:
        return self.role is not None and self.role.name == "admin"

    @property
    def is_active(self) -> bool:
        if self.deleted_at is not None or self.status == "banned":
            return False
        if self.status == "suspended":
            return self.suspended_until is not None and self.suspended_until <= utcnow()
        return True

    @hybrid_property
    def credit_balance(self) -> int:
        total = sum(entry.amount_delta for entry in self.credit_entries)
        return total

    @property
    def available_credit_balance(self) -> int:
        held = sum(
            hold.amount
            for hold in self.credit_holds
            if hold.status == "reserved"
        )
        return self.credit_balance - held

    def has_verified_skill(self, skill_id: int | None) -> bool:
        if not skill_id:
            return False
        return (
            self.certificates.filter_by(skill_id=skill_id, status="approved").count() > 0
        )

    def __repr__(self) -> str:
        return f"<User {self.email}>"


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return db.session.get(User, int(user_id))


class Profile(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    headline = db.Column(db.String(160))
    bio = db.Column(db.Text)
    location = db.Column(db.String(160))
    city = db.Column(db.String(80))
    country = db.Column(db.String(80))
    contact_email = db.Column(db.String(255))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    avatar_path = db.Column(db.String(255))
    reputation_score = db.Column(db.Float, default=0.0, nullable=False)
    review_count = db.Column(db.Integer, default=0, nullable=False)
    completed_exchange_count = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    user = db.relationship("User", back_populates="profile")


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    skills = db.relationship("Skill", back_populates="category", lazy="dynamic")
    listings = db.relationship("Listing", back_populates="category", lazy="dynamic")


class Skill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)

    category = db.relationship("Category", back_populates="skills")
    offered_by = db.relationship("UserSkillOffer", back_populates="skill", lazy="dynamic")
    wanted_by = db.relationship("UserSkillWant", back_populates="skill", lazy="dynamic")
    listings = db.relationship("Listing", back_populates="skill", lazy="dynamic")


class UserSkillOffer(db.Model):
    __table_args__ = (UniqueConstraint("user_id", "skill_id", name="uq_user_offered_skill"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey("skill.id"), nullable=False)
    note = db.Column(db.String(255))

    user = db.relationship("User", back_populates="offered_skills")
    skill = db.relationship("Skill", back_populates="offered_by")


class UserSkillWant(db.Model):
    __table_args__ = (UniqueConstraint("user_id", "skill_id", name="uq_user_wanted_skill"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey("skill.id"), nullable=False)
    note = db.Column(db.String(255))

    user = db.relationship("User", back_populates="wanted_skills")
    skill = db.relationship("Skill", back_populates="wanted_by")


class Certificate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey("skill.id"), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(32), default="pending", nullable=False)
    review_notes = db.Column(db.String(255))
    reviewed_at = db.Column(db.DateTime)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    user = db.relationship("User", foreign_keys=[user_id], back_populates="certificates")
    skill = db.relationship("Skill")
    reviewer = db.relationship("User", foreign_keys=[reviewer_id])


class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey("skill.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)
    title = db.Column(db.String(140), nullable=False)
    description = db.Column(db.Text, nullable=False)
    exchange_type = db.Column(db.String(16), nullable=False)
    min_credits = db.Column(db.Integer, default=0, nullable=False)
    location_text = db.Column(db.String(160))
    contact_method = db.Column(db.String(160))
    status = db.Column(db.String(32), default="pending", nullable=False)
    rejection_reason = db.Column(db.String(255))
    approved_at = db.Column(db.DateTime)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    user = db.relationship("User", foreign_keys=[user_id], back_populates="listings")
    skill = db.relationship("Skill", back_populates="listings")
    category = db.relationship("Category", back_populates="listings")
    reviewer = db.relationship("User", foreign_keys=[reviewer_id])
    availability = db.relationship(
        "ListingAvailability",
        back_populates="listing",
        cascade="all, delete-orphan",
    )
    requests = db.relationship(
        "ExchangeRequest",
        back_populates="listing",
        cascade="all, delete-orphan",
    )


class ListingAvailability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("listing.id"), nullable=False)
    label = db.Column(db.String(120), nullable=False)
    is_remote = db.Column(db.Boolean, default=False, nullable=False)

    listing = db.relationship("Listing", back_populates="availability")


class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seeker_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    partner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    overlap_summary = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    seeker = db.relationship("User", foreign_keys=[seeker_id])
    partner = db.relationship("User", foreign_keys=[partner_id])


class ExchangeRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("listing.id"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    request_type = db.Column(db.String(16), nullable=False)
    offered_skill_id = db.Column(db.Integer, db.ForeignKey("skill.id"))
    requested_message = db.Column(db.Text)
    credits_reserved = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(32), default="pending", nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    responded_at = db.Column(db.DateTime)

    listing = db.relationship("Listing", back_populates="requests")
    sender = db.relationship("User", foreign_keys=[sender_id], back_populates="sent_requests")
    recipient = db.relationship(
        "User",
        foreign_keys=[recipient_id],
        back_populates="received_requests",
    )
    offered_skill = db.relationship("Skill")
    credit_hold = db.relationship(
        "CreditHold",
        back_populates="request",
        uselist=False,
        cascade="all, delete-orphan",
    )
    exchange = db.relationship(
        "Exchange",
        back_populates="request",
        uselist=False,
        cascade="all, delete-orphan",
    )


class CreditHold(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("exchange_request.id"), unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(16), default="reserved", nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    released_at = db.Column(db.DateTime)

    request = db.relationship("ExchangeRequest", back_populates="credit_hold")
    user = db.relationship("User", back_populates="credit_holds")


class Exchange(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("exchange_request.id"), unique=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("listing.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    learner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    barter_skill_id = db.Column(db.Integer, db.ForeignKey("skill.id"))
    exchange_type = db.Column(db.String(16), nullable=False)
    status = db.Column(db.String(32), default="active", nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    completed_at = db.Column(db.DateTime)

    request = db.relationship("ExchangeRequest", back_populates="exchange")
    listing = db.relationship("Listing")
    teacher = db.relationship("User", foreign_keys=[teacher_id], back_populates="taught_exchanges")
    learner = db.relationship("User", foreign_keys=[learner_id], back_populates="learned_exchanges")
    barter_skill = db.relationship("Skill")
    completion_marks = db.relationship(
        "ExchangeCompletion",
        back_populates="exchange",
        cascade="all, delete-orphan",
    )
    conversation = db.relationship(
        "Conversation",
        back_populates="exchange",
        uselist=False,
        cascade="all, delete-orphan",
    )
    reviews = db.relationship("Review", back_populates="exchange", lazy="dynamic")


class ExchangeCompletion(db.Model):
    __table_args__ = (
        UniqueConstraint("exchange_id", "user_id", name="uq_exchange_completion_user"),
    )

    id = db.Column(db.Integer, primary_key=True)
    exchange_id = db.Column(db.Integer, db.ForeignKey("exchange.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    completed_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    exchange = db.relationship("Exchange", back_populates="completion_marks")
    user = db.relationship("User")


class Conversation(db.Model):
    __table_args__ = (
        UniqueConstraint("exchange_id", name="uq_conversation_exchange"),
        CheckConstraint("user_one_id != user_two_id", name="ck_distinct_conversation_users"),
    )

    id = db.Column(db.Integer, primary_key=True)
    exchange_id = db.Column(db.Integer, db.ForeignKey("exchange.id"))
    user_one_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user_two_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    subject = db.Column(db.String(140), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    exchange = db.relationship("Exchange", back_populates="conversation")
    user_one = db.relationship("User", foreign_keys=[user_one_id])
    user_two = db.relationship("User", foreign_keys=[user_two_id])
    messages = db.relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def other_participant(self, user_id: int) -> User | None:
        if self.user_one_id == user_id:
            return self.user_two
        if self.user_two_id == user_id:
            return self.user_one
        return None


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversation.id"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    conversation = db.relationship("Conversation", back_populates="messages")
    sender = db.relationship("User", back_populates="sent_messages")
    reads = db.relationship(
        "MessageRead",
        back_populates="message",
        cascade="all, delete-orphan",
    )


class MessageRead(db.Model):
    __table_args__ = (UniqueConstraint("message_id", "user_id", name="uq_message_read_user"),)

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("message.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    read_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    message = db.relationship("Message", back_populates="reads")
    user = db.relationship("User")


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    kind = db.Column(db.String(32), default="info", nullable=False)
    title = db.Column(db.String(140), nullable=False)
    body = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    read_at = db.Column(db.DateTime)

    user = db.relationship("User", back_populates="notifications")


class Review(db.Model):
    __table_args__ = (
        UniqueConstraint("exchange_id", "reviewer_id", name="uq_exchange_reviewer"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_rating_range"),
    )

    id = db.Column(db.Integer, primary_key=True)
    exchange_id = db.Column(db.Integer, db.ForeignKey("exchange.id"), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reviewee_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    exchange = db.relationship("Exchange", back_populates="reviews")
    reviewer = db.relationship("User", foreign_keys=[reviewer_id], back_populates="reviews_written")
    reviewee = db.relationship("User", foreign_keys=[reviewee_id], back_populates="reviews_received")


class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reported_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reason = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(32), default="open", nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime)

    reporter = db.relationship("User", foreign_keys=[reporter_id], back_populates="reports_filed")
    reported_user = db.relationship(
        "User",
        foreign_keys=[reported_user_id],
        back_populates="reports_against",
    )


class CreditLedger(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    amount_delta = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    entry_type = db.Column(db.String(32), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    related_request_id = db.Column(db.Integer, db.ForeignKey("exchange_request.id"))
    related_exchange_id = db.Column(db.Integer, db.ForeignKey("exchange.id"))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    user = db.relationship("User", back_populates="credit_entries")


class AdminAuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    action = db.Column(db.String(80), nullable=False)
    target_type = db.Column(db.String(80), nullable=False)
    target_id = db.Column(db.Integer)
    detail = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    admin = db.relationship("User")


class AccountDeletionRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String(32), default="pending", nullable=False)
    requested_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    scheduled_purge_at = db.Column(db.DateTime, nullable=False)
    cancelled_at = db.Column(db.DateTime)
    processed_at = db.Column(db.DateTime)

    user = db.relationship("User", back_populates="deletion_requests")


def refresh_profile_metrics(user: User) -> None:
    ratings = [review.rating for review in user.reviews_received]
    user.profile.reputation_score = round(mean(ratings), 1) if ratings else 0.0
    user.profile.review_count = len(ratings)
    completed = user.taught_exchanges.filter_by(status="completed").count() + user.learned_exchanges.filter_by(
        status="completed"
    ).count()
    user.profile.completed_exchange_count = completed


def unread_message_count(user: User) -> int:
    return (
        db.session.query(func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(
            ((Conversation.user_one_id == user.id) | (Conversation.user_two_id == user.id))
            & (Message.sender_id != user.id)
            & (~Message.reads.any(MessageRead.user_id == user.id))
        )
        .scalar()
        or 0
    )
