from __future__ import annotations

from datetime import datetime

from app.models.user import Role, User, unique_username
from app.utils.passwords import hash_password

from .base_repository import BaseRepository
from .profile_repository import ProfileRepository
from .role_repository import RoleRepository


class UserRepository(BaseRepository):
    def __init__(
        self,
        db_factory=None,
        *,
        role_repository: RoleRepository | None = None,
        profile_repository: ProfileRepository | None = None,
    ):
        super().__init__(db_factory)
        self._role_repository = role_repository or RoleRepository(db_factory)
        self._profile_repository = profile_repository or ProfileRepository(db_factory)

    def find_by_email(self, email: str) -> User | None:
        normalized_email = self._normalize_email(email)
        with self._db() as db:
            row = db.fetch_one("SELECT * FROM users WHERE email = %s", (normalized_email,))
        return self._hydrate(row)

    def find_by_id(self, user_id: int) -> User | None:
        with self._db() as db:
            row = db.fetch_one("SELECT * FROM users WHERE id = %s", (user_id,))
        return self._hydrate(row)

    def all(self) -> list[User]:
        with self._db() as db:
            rows = db.fetch_all("SELECT * FROM users ORDER BY created_at DESC")
        return [user for row in rows if (user := self._hydrate(row))]

    def count(self) -> int:
        with self._db() as db:
            row = db.fetch_one("SELECT COUNT(*) AS count FROM users")
        return int((row or {}).get("count") or 0)

    def verified_count(self) -> int:
        with self._db() as db:
            row = db.fetch_one("SELECT COUNT(*) AS count FROM users WHERE is_email_verified = TRUE")
        return int((row or {}).get("count") or 0)

    def create_registered(self, full_name: str, email: str, password: str, location: str, role: Role) -> User:
        normalized_email = self._normalize_email(email)
        username = unique_username(normalized_email.split("@")[0], self._profile_repository)
        password_hash = hash_password(password)
        with self._db() as db:
            with db.transaction():
                user_id = db.execute(
                    """
                    INSERT INTO users (full_name, email, password_hash, role_id)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (full_name, normalized_email, password_hash, role.id),
                )
                db.execute(
                    """
                    INSERT INTO profiles (user_id, username, location, contact_email)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (user_id, username, location, normalized_email),
                )
                row = db.fetch_one("SELECT * FROM users WHERE id = %s", (user_id,))
        return self._hydrate(row)

    def update_password(self, user: User) -> None:
        user._reset_login_security()
        with self._db() as db:
            db.execute(
                """
                UPDATE users
                SET password_hash = %s,
                    failed_login_count = 0,
                    locked_until = NULL
                WHERE id = %s
                """,
                (user.password_hash, user.id),
            )

    def create_password_reset_token(self, user: User, token_hash: str, expires_at: datetime) -> None:
        now = datetime.utcnow()
        with self._db() as db:
            with db.transaction():
                db.execute(
                    """
                    UPDATE password_reset_tokens
                    SET used_at = %s
                    WHERE user_id = %s AND used_at IS NULL
                    """,
                    (now, user.id),
                )
                db.execute(
                    """
                    INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
                    VALUES (%s, %s, %s)
                    """,
                    (user.id, token_hash, expires_at),
                )

    def has_valid_password_reset_token(self, token_hash: str) -> bool:
        with self._db() as db:
            row = db.fetch_one(
                """
                SELECT id
                FROM password_reset_tokens
                WHERE token_hash = %s
                  AND used_at IS NULL
                  AND expires_at > %s
                """,
                (token_hash, datetime.utcnow()),
            )
        return row is not None

    def consume_password_reset_token(self, token_hash: str, password_hash: str) -> bool:
        now = datetime.utcnow()
        with self._db() as db:
            with db.transaction():
                row = db.fetch_one(
                    """
                    SELECT id, user_id, expires_at, used_at
                    FROM password_reset_tokens
                    WHERE token_hash = %s
                    """,
                    (token_hash,),
                )
                if (
                    not row
                    or row.get("used_at") is not None
                    or row.get("expires_at") is None
                    or row["expires_at"] <= now
                ):
                    return False
                db.execute(
                    """
                    UPDATE users
                    SET password_hash = %s,
                        failed_login_count = 0,
                        locked_until = NULL
                    WHERE id = %s
                    """,
                    (password_hash, row["user_id"]),
                )
                db.execute(
                    "UPDATE password_reset_tokens SET used_at = %s WHERE id = %s",
                    (now, row["id"]),
                )
        return True

    def save_verification_token(self, user: User, token: str, expires_at: datetime) -> None:
        user._assign_verification_token(token, expires_at)
        with self._db() as db:
            db.execute(
                "UPDATE users SET verification_token = %s, verification_token_expires = %s WHERE id = %s",
                (token, expires_at, user.id),
            )

    def mark_email_verified(self, user: User) -> None:
        user._mark_email_verified()
        with self._db() as db:
            db.execute(
                """
                UPDATE users
                SET is_email_verified = TRUE, verification_token = NULL, verification_token_expires = NULL
                WHERE id = %s
                """,
                (user.id,),
            )

    def register_failed_login(self, user: User, locked_until: datetime | None = None) -> None:
        user._record_failed_login(locked_until)
        self._persist_login_security(user)

    def clear_failed_login(self, user: User) -> None:
        user._reset_login_security()
        self._persist_login_security(user)

    def update_role(self, user: User, role: Role) -> None:
        user._assign_role(role)
        with self._db() as db:
            db.execute("UPDATE users SET role_id = %s WHERE id = %s", (role.id, user.id))

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.lower().strip()

    def _hydrate(self, row: dict | None) -> User | None:
        if not row:
            return None
        role = self._role_repository.find_by_id(row["role_id"])
        profile = self._profile_repository.find_by_user_id(row["id"])
        return User(
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

    def _persist_login_security(self, user: User) -> None:
        with self._db() as db:
            db.execute(
                "UPDATE users SET failed_login_count = %s, locked_until = %s WHERE id = %s",
                (user.failed_login_count, user.locked_until, user.id),
            )

    def update_status(self, user_id: int, status: str, suspended_until: datetime | None = None, suspension_reason: str | None = None) -> None:
        with self._db() as db:
            db.execute(
                """
                UPDATE users
                SET status = %s,
                    suspended_until = %s,
                    suspension_reason = %s
                WHERE id = %s
                """,
                (status, suspended_until, suspension_reason, user_id),
            )
