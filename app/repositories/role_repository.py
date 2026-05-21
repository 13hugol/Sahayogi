from __future__ import annotations

from app.enums import UserRole
from app.models.user import Role

from .base_repository import BaseRepository


class RoleRepository(BaseRepository):
    def find_by_name(self, name: str | UserRole) -> Role | None:
        normalized_name = self._normalize_name(name)
        with self._db() as db:
            row = db.fetch_one("SELECT * FROM roles WHERE name = %s", (normalized_name,))
        return Role.from_row(row)

    def find_by_id(self, role_id: int) -> Role | None:
        with self._db() as db:
            row = db.fetch_one("SELECT * FROM roles WHERE id = %s", (role_id,))
        return Role.from_row(row)

    def ensure(self, name: str | UserRole, description: str | None = None) -> Role:
        normalized_name = self._normalize_name(name)
        role = self.find_by_name(normalized_name)
        if role:
            return role
        resolved_description = description or self._description_for(normalized_name)
        with self._db() as db:
            role_id = db.execute(
                "INSERT INTO roles (name, description) VALUES (%s, %s)",
                (normalized_name, resolved_description),
            )
        return Role(id=role_id, name=normalized_name, description=resolved_description)

    def count_by_name(self, name: str | UserRole) -> int:
        normalized_name = self._normalize_name(name)
        with self._db() as db:
            row = db.fetch_one(
                """
                SELECT COUNT(*) AS count
                FROM users
                INNER JOIN roles ON users.role_id = roles.id
                WHERE roles.name = %s
                """,
                (normalized_name,),
            )
        return int((row or {}).get("count") or 0)

    @staticmethod
    def _normalize_name(name: str | UserRole) -> str:
        if isinstance(name, UserRole):
            return name.value
        return str(name).strip().lower()

    @staticmethod
    def _description_for(name: str) -> str:
        mapping = {
            UserRole.ADMIN.value: UserRole.ADMIN.description,
            UserRole.USER.value: UserRole.USER.description,
        }
        return mapping.get(name, name.replace("_", " ").title())

