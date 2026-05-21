from __future__ import annotations

from app.enums import UserRole

from .base_validator import BaseValidator


class RoleAssignmentValidator(BaseValidator):
    def validate(self, role_name: str) -> dict[str, str]:
        normalized_role = str(role_name).strip().lower()
        if normalized_role in UserRole.values():
            return {}
        return {"role": "Invalid role."}

