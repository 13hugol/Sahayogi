from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.database import Database
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
        db = Database()
        try:
            row = db.fetch_one("SELECT * FROM roles WHERE name = %s", (name,))
            return cls.from_row(row)
        finally:
            db.close()

    @classmethod
    def find_by_id(cls, role_id: int) -> "Role | None":
        db = Database()
        try:
            row = db.fetch_one("SELECT * FROM roles WHERE id = %s", (role_id,))
            return cls.from_row(row)
        finally:
            db.close()

    @classmethod
    def ensure(cls, name: str, description: str) -> "Role":
        role = cls.find_by_name(name)
        if role:
            return role
        db = Database()
        try:
            role_id = db.execute(
                "INSERT INTO roles (name, description) VALUES (%s, %s)",
                (name, description),
            )
            return cls(id=role_id, name=name, description=description)
        finally:
            db.close()

    @classmethod
    def count_by_name(cls, name: str) -> int:
        db = Database()
        try:
            row = db.fetch_one(
                """
                SELECT COUNT(*) AS count
                FROM users
                INNER JOIN roles ON users.role_id = roles.id
                WHERE roles.name = %s
                """,
                (name,),
            )
            return int(row["count"])
        finally:
            db.close()


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
        db = Database()
        try:
            row = db.fetch_one("SELECT * FROM profiles WHERE user_id = %s", (user_id,))
            return cls.from_row(row)
        finally:
            db.close()

    @classmethod
    def create(cls, user_id: int, username: str, location: str, contact_email: str) -> None:
        db = Database()
        try:
            db.execute(
                """
                INSERT INTO profiles (user_id, username, location, contact_email)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, username, location, contact_email),
            )
        finally:
            db.close()

    @classmethod
    def username_exists(cls, username: str) -> bool:
        db = Database()
        try:
            row = db.fetch_one("SELECT user_id FROM profiles WHERE username = %s", (username,))
            return row is not None
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
    ):
        self.id = id
        self.full_name = full_name
        self.email = email
        self.password_hash = password_hash
        self.is_email_verified = bool(is_email_verified)
        self.status = status
        self.role_id = role_id
        self.failed_login_count = failed_login_count
        self.locked_until = locked_until
        self.verification_token = verification_token
        self.verification_token_expires = verification_token_expires
        self.created_at = created_at
        self.role = role
        self.profile = profile

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
        )

    @classmethod
    def find_by_email(cls, email: str) -> "User | None":
        db = Database()
        try:
            row = db.fetch_one("SELECT * FROM users WHERE email = %s", (email.lower().strip(),))
            return cls.from_row(row)
        finally:
            db.close()

    @classmethod
    def find_by_id(cls, user_id: int) -> "User | None":
        db = Database()
        try:
            row = db.fetch_one("SELECT * FROM users WHERE id = %s", (user_id,))
            return cls.from_row(row)
        finally:
            db.close()

    @classmethod
    def all(cls) -> list["User"]:
        db = Database()
        try:
            rows = db.fetch_all("SELECT * FROM users ORDER BY created_at DESC")
            return [cls.from_row(row) for row in rows if row]
        finally:
            db.close()

    @classmethod
    def count(cls) -> int:
        db = Database()
        try:
            row = db.fetch_one("SELECT COUNT(*) AS count FROM users")
            return int(row["count"])
        finally:
            db.close()

    @classmethod
    def verified_count(cls) -> int:
        db = Database()
        try:
            row = db.fetch_one("SELECT COUNT(*) AS count FROM users WHERE is_email_verified = TRUE")
            return int(row["count"])
        finally:
            db.close()

    @classmethod
    def create_registered(cls, full_name: str, email: str, password: str, location: str, role: Role) -> "User":
        password_hash = generate_password_hash(password)
        username = unique_username(email.split("@")[0])
        db = Database()
        try:
            user_id = db.execute(
                """
                INSERT INTO users (full_name, email, password_hash, role_id)
                VALUES (%s, %s, %s, %s)
                """,
                (full_name, email.lower().strip(), password_hash, role.id),
            )
            Profile.create(user_id, username, location, email.lower().strip())
            return cls.find_by_id(user_id)
        finally:
            db.close()

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)
        db = Database()
        try:
            db.execute("UPDATE users SET password_hash = %s WHERE id = %s", (self.password_hash, self.id))
        finally:
            db.close()

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def save_verification_token(self, token: str, expires_at: datetime) -> None:
        self.verification_token = token
        self.verification_token_expires = expires_at
        db = Database()
        try:
            db.execute(
                "UPDATE users SET verification_token = %s, verification_token_expires = %s WHERE id = %s",
                (token, expires_at, self.id),
            )
        finally:
            db.close()

    def mark_email_verified(self) -> None:
        self.is_email_verified = True
        db = Database()
        try:
            db.execute(
                """
                UPDATE users
                SET is_email_verified = TRUE, verification_token = NULL, verification_token_expires = NULL
                WHERE id = %s
                """,
                (self.id,),
            )
        finally:
            db.close()

    def register_failed_login(self, locked_until: datetime | None = None) -> None:
        self.failed_login_count = 0 if locked_until else self.failed_login_count + 1
        self.locked_until = locked_until
        db = Database()
        try:
            db.execute(
                "UPDATE users SET failed_login_count = %s, locked_until = %s WHERE id = %s",
                (self.failed_login_count, locked_until, self.id),
            )
        finally:
            db.close()

    def clear_failed_login(self) -> None:
        self.failed_login_count = 0
        self.locked_until = None
        db = Database()
        try:
            db.execute(
                "UPDATE users SET failed_login_count = 0, locked_until = NULL WHERE id = %s",
                (self.id,),
            )
        finally:
            db.close()

    def update_role(self, role: Role) -> None:
        self.role = role
        self.role_id = role.id
        db = Database()
        try:
            db.execute("UPDATE users SET role_id = %s WHERE id = %s", (role.id, self.id))
        finally:
            db.close()

    @property
    def is_admin(self) -> bool:
        return self.role is not None and self.role.name == "admin"

    @property
    def available_credit_balance(self) -> int:
        return 0

    @property
    def offered_skills(self) -> list:
        from .profile import ProfileSkill

        return ProfileSkill.find_for_user(self.id, "offered")

    @property
    def wanted_skills(self) -> list:
        from .profile import ProfileSkill

        return ProfileSkill.find_for_user(self.id, "wanted")

    def has_verified_skill(self, _skill_id: int) -> bool:
        return False


def unique_username(base: str) -> str:
    clean = "".join(ch.lower() for ch in base if ch.isalnum())[:20] or "member"
    username = clean
    counter = 1
    while Profile.username_exists(username):
        counter += 1
        username = f"{clean}{counter}"
    return username
