from __future__ import annotations

from app.dto import DashboardStats
from app.enums import UserRole
from app.exceptions import CategoryNotFoundError, InvalidRoleError, SelfRoleChangeError, UserNotFoundError
from app.repositories import AdminAuditRepository, CategoryRepository, RoleRepository, UserRepository


class AdminService:
    def __init__(
        self,
        user_repository: UserRepository,
        role_repository: RoleRepository,
        audit_repository: AdminAuditRepository,
        category_repository: CategoryRepository | None = None,
    ):
        self._user_repository = user_repository
        self._role_repository = role_repository
        self._audit_repository = audit_repository
        self._category_repository = category_repository or CategoryRepository()

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

    def list_categories(self):
        return self._category_repository.all()

    def find_category(self, category_id: int | None):
        if category_id is None:
            return None
        return self._category_repository.find_by_id(category_id)

    def category_name_exists(self, name: str, *, exclude_id: int | None = None) -> bool:
        return self._category_repository.name_exists(name, exclude_id=exclude_id)

    def category_slug_exists(self, slug: str, *, exclude_id: int | None = None) -> bool:
        return self._category_repository.slug_exists(slug, exclude_id=exclude_id)

    def create_category(self, *, admin_user, name: str, slug: str, icon: str, description: str):
        category = self._category_repository.create(
            name=name,
            slug=slug,
            icon=icon,
            description=description,
        )
        self._audit_repository.create(
            admin_id=admin_user.id,
            action="create_category",
            target_type="Category",
            target_id=category.id,
            detail=f"Category '{category.name}' created by admin {admin_user.email}",
        )
        return category

    def update_category(self, *, admin_user, category_id: int, name: str, slug: str, icon: str, description: str):
        previous = self._category_repository.find_by_id(category_id)
        if not previous:
            raise CategoryNotFoundError(category_id)

        category = self._category_repository.update(
            category_id,
            name=name,
            slug=slug,
            icon=icon,
            description=description,
        )
        if not category:
            raise CategoryNotFoundError(category_id)

        self._audit_repository.create(
            admin_id=admin_user.id,
            action="rename_category",
            target_type="Category",
            target_id=category.id,
            detail=(
                f"Category '{previous.name}' renamed to '{category.name}' "
                f"by admin {admin_user.email}"
            ),
        )
        return category

