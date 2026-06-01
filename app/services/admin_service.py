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
        skill_repository=None,
    ):
        self._user_repository = user_repository
        self._role_repository = role_repository
        self._audit_repository = audit_repository
        from app.repositories import SkillRepository
        self._skill_repository = skill_repository or SkillRepository()

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

    def get_pending_listings(
        self,
        category_id: int | None = None,
        username: str | None = None,
        sort_order: str = "desc",
    ):
        from app.models.skill import Skill
        sql = """
            SELECT s.* FROM skills s
            JOIN profiles p ON s.user_id = p.user_id
            WHERE s.status = 'pending'
        """
        params = []
        if category_id is not None:
            sql += " AND s.category_id = %s"
            params.append(category_id)
        if username:
            sql += " AND p.username = %s"
            params.append(username)
        
        if sort_order.lower() == "asc":
            sql += " ORDER BY s.created_at ASC"
        else:
            sql += " ORDER BY s.created_at DESC"

        with self._skill_repository._db() as db:
            rows = db.fetch_all(sql, params)
        return [Skill.from_row(row) for row in rows if row]

    def approve_listing(self, admin_user, listing_id: int):
        listing = self._skill_repository.find_by_id(listing_id)
        if not listing:
            return None
        listing.status = "approved"
        listing.rejection_reason = None
        self._skill_repository.update(listing)
        
        self._audit_repository.create(
            admin_id=admin_user.id,
            action="approve_listing",
            target_type="Skill",
            target_id=listing.id,
            detail=f"Listing '{listing.title}' approved by admin {admin_user.email}",
        )
        return listing

    def reject_listing(self, admin_user, listing_id: int, reason: str):
        listing = self._skill_repository.find_by_id(listing_id)
        if not listing:
            return None
        listing.status = "rejected"
        listing.rejection_reason = reason
        self._skill_repository.update(listing)
        
        self._audit_repository.create(
            admin_id=admin_user.id,
            action="reject_listing",
            target_type="Skill",
            target_id=listing.id,
            detail=f"Listing '{listing.title}' rejected by admin {admin_user.email} (Reason: {reason})",
        )
        return listing

    def list_reports(self):
        from app.repositories import ReportRepository
        return ReportRepository().list_all()

    def resolve_report(self, admin_user, report_id: int, decision: str):
        from app.repositories import ReportRepository
        report_repo = ReportRepository()
        report = report_repo.find_by_id(report_id)
        if not report:
            return None
        
        # update status
        status = "resolved" if decision == "resolved" else "dismissed"
        report_repo.update_status(report_id, status)
        report.status = status
        
        # audit log
        self._audit_repository.create(
            admin_id=admin_user.id,
            action="resolve_report",
            target_type="Report",
            target_id=report_id,
            detail=f"Report against {report.reported_user.full_name if report.reported_user else 'Unknown'} marked as {status} by admin {admin_user.email}",
        )
        return report

