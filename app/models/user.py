from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math

from flask_login import UserMixin
from app.enums import SkillType, UserRole
from app.utils.passwords import hash_password, verify_password

from .base_model import BaseModel


@dataclass
class Role(BaseModel):
    id: int
    name: str
    description: str | None = None

    @classmethod
    def from_row(cls, row: dict | None) -> "Role | None":
        if not row:
            return None
        return cls(id=row["id"], name=row["name"], description=row.get("description"))

    @classmethod
    def find_by_name(cls, name: str) -> "Role | None":
        from app.repositories import RoleRepository

        return RoleRepository().find_by_name(name)

    @classmethod
    def find_by_id(cls, role_id: int) -> "Role | None":
        from app.repositories import RoleRepository

        return RoleRepository().find_by_id(role_id)

    @classmethod
    def ensure(cls, name: str, description: str | None = None) -> "Role":
        from app.repositories import RoleRepository

        return RoleRepository().ensure(name, description)

    @classmethod
    def count_by_name(cls, name: str) -> int:
        from app.repositories import RoleRepository

        return RoleRepository().count_by_name(name)


@dataclass
class Profile(BaseModel):
    user_id: int
    username: str
    location: str | None = None
    contact_email: str | None = None
    avatar_path: str | None = None
    headline: str | None = None
    bio: str | None = None
    reputation_score: float = 0.0
    review_count: int = 0
    completed_exchange_count: int = 0

    @classmethod
    def from_row(cls, row: dict | None) -> "Profile | None":
        if not row:
            return None
        return cls(
            user_id=row["user_id"],
            username=row["username"],
            location=row.get("location"),
            contact_email=row.get("contact_email"),
            avatar_path=row.get("avatar_path"),
            headline=row.get("headline"),
            bio=row.get("bio"),
            reputation_score=float(row.get("reputation_score") or 0),
            review_count=int(row.get("review_count") or 0),
            completed_exchange_count=int(row.get("completed_exchange_count") or 0),
        )

    @classmethod
    def find_by_user_id(cls, user_id: int) -> "Profile | None":
        from app.repositories import ProfileRepository

        return ProfileRepository().find_by_user_id(user_id)

    @classmethod
    def create(cls, user_id: int, username: str, location: str, contact_email: str) -> None:
        from app.repositories import ProfileRepository

        ProfileRepository().create(user_id, username, location, contact_email)

    @classmethod
    def username_exists(cls, username: str) -> bool:
        from app.repositories import ProfileRepository

        return ProfileRepository().username_exists(username)

    @classmethod
    def update_details(
        cls,
        user_id: int,
        *,
        location: str,
        bio: str,
        avatar_path: str | None = None,
    ) -> None:
        fields = ["location = %s", "bio = %s"]
        params: list[str | int | None] = [location.strip(), bio.strip() or None]
        if avatar_path:
            fields.append("avatar_path = %s")
            params.append(avatar_path)
        params.append(user_id)

        from app.database import Database

        db = Database()
        try:
            db.execute(
                f"UPDATE profiles SET {', '.join(fields)} WHERE user_id = %s",
                tuple(params),
            )
        finally:
            db.close()


class User(UserMixin, BaseModel):
    def __init__(
        self,
        *,
        id: int,
        full_name: str,
        email: str,
        password_hash: str,
        is_email_verified: bool,
        status: str,
        role_id: int,
        failed_login_count: int = 0,
        locked_until: datetime | None = None,
        verification_token: str | None = None,
        verification_token_expires: datetime | None = None,
        created_at: datetime | None = None,
        role: Role | None = None,
        profile: Profile | None = None,
        suspended_until: datetime | None = None,
        suspension_reason: str | None = None,
        credit_balance: int = 100,
    ):
        self.id = id
        self.full_name = full_name
        self.email = email
        self._password_hash = password_hash
        self.is_email_verified = bool(is_email_verified)
        self.status = status
        self.role_id = role_id
        self._failed_login_count = int(failed_login_count or 0)
        self._locked_until = locked_until
        self.verification_token = verification_token
        self.verification_token_expires = verification_token_expires
        self.created_at = created_at
        self.role = role
        self.profile = profile
        self.suspended_until = suspended_until
        self.suspension_reason = suspension_reason
        self.credit_balance = credit_balance

    @classmethod
    def from_row(cls, row: dict | None) -> "User | None":
        if not row:
            return None
        role = Role.find_by_id(row["role_id"])
        profile = Profile.find_by_user_id(row["id"])
        return cls(
            id=row["id"],
            full_name=row["full_name"],
            email=row["email"],
            password_hash=row["password_hash"],
            is_email_verified=row["is_email_verified"],
            status=row["status"],
            role_id=row["role_id"],
            failed_login_count=row.get("failed_login_count") or 0,
            locked_until=row.get("locked_until"),
            verification_token=row.get("verification_token"),
            verification_token_expires=row.get("verification_token_expires"),
            created_at=row.get("created_at"),
            role=role,
            profile=profile,
            suspended_until=row.get("suspended_until"),
            suspension_reason=row.get("suspension_reason"),
            credit_balance=int(row.get("credit_balance") if row.get("credit_balance") is not None else 100),
        )

    @classmethod
    def find_by_email(cls, email: str) -> "User | None":
        from app.repositories import UserRepository

        return UserRepository().find_by_email(email)

    @classmethod
    def find_by_id(cls, user_id: int) -> "User | None":
        from app.repositories import UserRepository

        return UserRepository().find_by_id(user_id)

    @classmethod
    def all(cls) -> list["User"]:
        from app.repositories import UserRepository

        return UserRepository().all()

    @classmethod
    def update_full_name(cls, user_id: int, full_name: str) -> None:
        from app.database import Database

        db = Database()
        try:
            db.execute("UPDATE users SET full_name = %s WHERE id = %s", (full_name.strip(), user_id))
        finally:
            db.close()

    @classmethod
    def count(cls) -> int:
        from app.repositories import UserRepository

        return UserRepository().count()

    @classmethod
    def verified_count(cls) -> int:
        from app.repositories import UserRepository

        return UserRepository().verified_count()

    @classmethod
    def create_registered(cls, full_name: str, email: str, password: str, location: str, role: Role) -> "User":
        from app.repositories import UserRepository

        return UserRepository().create_registered(full_name, email, password, location, role)

    @property
    def password_hash(self) -> str:
        return self._password_hash

    @property
    def failed_login_count(self) -> int:
        return self._failed_login_count

    @property
    def locked_until(self) -> datetime | None:
        return self._locked_until

    @property
    def is_locked(self) -> bool:
        return self._locked_until is not None and self._locked_until > datetime.utcnow()

    @property
    def has_lockout_expired(self) -> bool:
        return self._locked_until is not None and self._locked_until <= datetime.utcnow()

    def minutes_until_unlock(self) -> int:
        if not self.is_locked or self._locked_until is None:
            return 0
        remaining = self._locked_until - datetime.utcnow()
        return max(1, math.ceil(remaining.total_seconds() / 60))

    def _set_password_hash(self, password_hash: str) -> None:
        self._password_hash = password_hash

    def _assign_verification_token(self, token: str, expires_at: datetime) -> None:
        self.verification_token = token
        self.verification_token_expires = expires_at

    def _mark_email_verified(self) -> None:
        self.is_email_verified = True
        self.verification_token = None
        self.verification_token_expires = None

    def _record_failed_login(self, locked_until: datetime | None = None) -> None:
        self._failed_login_count += 1
        self._locked_until = locked_until

    def _reset_login_security(self) -> None:
        self._failed_login_count = 0
        self._locked_until = None

    def _assign_role(self, role: Role) -> None:
        self.role = role
        self.role_id = role.id

    def set_password(self, password: str) -> None:
        from app.repositories import UserRepository

        self._set_password_hash(hash_password(password))
        UserRepository().update_password(self)

    def check_password(self, password: str) -> bool:
        return self._check_password(password)

    def _check_password(self, password: str) -> bool:
        return verify_password(self._password_hash, password)

    def save_verification_token(self, token: str, expires_at: datetime) -> None:
        from app.repositories import UserRepository

        UserRepository().save_verification_token(self, token, expires_at)

    def mark_email_verified(self) -> None:
        from app.repositories import UserRepository

        UserRepository().mark_email_verified(self)

    def register_failed_login(self, locked_until: datetime | None = None) -> None:
        from app.repositories import UserRepository

        UserRepository().register_failed_login(self, locked_until)

    def clear_failed_login(self) -> None:
        from app.repositories import UserRepository

        UserRepository().clear_failed_login(self)

    def update_role(self, role: Role) -> None:
        from app.repositories import UserRepository

        UserRepository().update_role(self, role)

    @property
    def is_admin(self) -> bool:
        return self.role is not None and self.role.name == UserRole.ADMIN.value

    @property
    def available_credit_balance(self) -> int:
        from app.database import Database
        db = Database()
        try:
            row = db.fetch_one(
                "SELECT COALESCE(SUM(amount), 0) AS active_holds FROM credit_holds WHERE user_id = %s AND status = 'active'",
                (self.id,),
            )
            holds = int((row or {}).get("active_holds") or 0)
            return self.credit_balance - holds
        finally:
            db.close()

    @property
    def offered_skills(self) -> list:
        from .profile import ProfileSkill

        return ProfileSkill.find_for_user(self.id, SkillType.OFFERED)

    @property
    def wanted_skills(self) -> list:
        from .profile import ProfileSkill

        return ProfileSkill.find_for_user(self.id, SkillType.WANTED)

    def has_verified_skill(self, skill_id: int) -> bool:
        return any(skill.id == skill_id and skill.has_verified_certificate for skill in self.offered_skills)


def unique_username(base: str, profile_repository=None) -> str:
    if profile_repository is None:
        from app.repositories import ProfileRepository

        profile_repository = ProfileRepository()
    clean = "".join(ch.lower() for ch in base if ch.isalnum())[:20] or "member"
    username = clean
    counter = 1
    while profile_repository.username_exists(username):
        counter += 1
        username = f"{clean}{counter}"
    return username
