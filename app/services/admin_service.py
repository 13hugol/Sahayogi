from __future__ import annotations

from app.dto import DashboardStats
from app.enums import UserRole
from app.exceptions import InvalidRoleError, SelfRoleChangeError, UserNotFoundError
from app.repositories import AdminAuditRepository, RoleRepository, UserRepository


class AdminService:
    def __init__(
        self,
        user_repository: UserRepository,
        role_repository: RoleRepository,
        audit_repository: AdminAuditRepository,
    ):
        self._user_repository = user_repository
        self._role_repository = role_repository
        self._audit_repository = audit_repository

    def dashboard_stats(self) -> DashboardStats:
        return DashboardStats(
            total_users=self._user_repository.count(),
            admin_users=self._role_repository.count_by_name(UserRole.ADMIN),
            regular_users=self._role_repository.count_by_name(UserRole.USER),
            verified_users=self._user_repository.verified_count(),
            audit_logs=self._audit_repository.count(),
        )

    def list_users(self):
        return self._user_repository.all()

    def find_user(self, user_id: int | None):
        if not user_id:
            return None
        return self._user_repository.find_by_id(user_id)

    def update_user_role(self, *, admin_user, target_user_id: int, new_role_name: str):
        target_user = self._user_repository.find_by_id(target_user_id)
        if not target_user:
            raise UserNotFoundError()
        if target_user.id == admin_user.id:
            raise SelfRoleChangeError()

        normalized_role = str(new_role_name).strip().lower()
        if normalized_role not in UserRole.values():
            raise InvalidRoleError(normalized_role)

        old_role_name = target_user.role.name if target_user.role else "unknown"
        new_role = self._role_repository.ensure(normalized_role)
        self._user_repository.update_role(target_user, new_role)
        self._audit_repository.create(
            admin_id=admin_user.id,
            action="update_user_role",
            target_type="User",
            target_id=target_user.id,
            detail=f"Role changed from '{old_role_name}' to '{normalized_role}' by admin {admin_user.email}",
        )
        return target_user

