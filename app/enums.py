from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"

    @property
    def description(self) -> str:
        descriptions = {
            UserRole.ADMIN: "Administrator",
            UserRole.USER: "Platform member",
        }
        return descriptions[self]

    @classmethod
    def values(cls) -> set[str]:
        return {role.value for role in cls}


class AccountStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BANNED = "banned"
    DELETED = "deleted"


class SkillType(str, Enum):
    OFFERED = "offered"
    WANTED = "wanted"

    @classmethod
    def values(cls) -> set[str]:
        return {skill_type.value for skill_type in cls}


class CertificateStatus(str, Enum):
    NONE = "none"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

