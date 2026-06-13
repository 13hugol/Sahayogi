from __future__ import annotations

from flask import Blueprint

from ..controllers.admin_controller import AdminController
from ..repositories import AdminAuditRepository, ProfileRepository, RoleRepository, UserRepository
from ..services import AdminService
from ..validators import RoleAssignmentValidator


class AdminRoutes:
    def __init__(self):
        self.bp = Blueprint("admin", __name__, url_prefix="/admin")
        role_repository = RoleRepository()
        profile_repository = ProfileRepository()
        user_repository = UserRepository(
            role_repository=role_repository,
            profile_repository=profile_repository,
        )
        self.controller = AdminController(
            AdminService(user_repository, role_repository, AdminAuditRepository()),
            RoleAssignmentValidator(),
        )

    def register(self):
        self.bp.route("/")(self.controller.dashboard)
        self.bp.route("/users")(self.controller.users)
        self.bp.route("/users/<int:user_id>/role", methods=["POST"])(self.controller.update_user_role)
        self.bp.route("/users/<int:user_id>/suspend", methods=["POST"])(self.controller.suspend_user)
        self.bp.route("/users/<int:user_id>/ban", methods=["POST"])(self.controller.ban_user)
        self.bp.route("/users/<int:user_id>/unsuspend", methods=["POST"])(self.controller.unsuspend_user)
        self.bp.route("/listings")(self.controller.listings)
        self.bp.route("/listings/<int:listing_id>/approve", methods=["POST"])(self.controller.approve_listing)
        self.bp.route("/listings/<int:listing_id>/reject", methods=["POST"])(self.controller.reject_listing)
        self.bp.route("/certificates")(self.controller.certificates)
        self.bp.route("/reports")(self.controller.reports)
        self.bp.route("/reports/<int:report_id>/resolve", methods=["POST"])(self.controller.resolve_report)
        self.bp.route("/reviews")(self.controller.reviews)
        self.bp.route("/reviews/<int:review_id>/reject", methods=["POST"])(self.controller.reject_review)
        self.bp.route("/categories", methods=["GET", "POST"])(self.controller.categories)
        self.bp.route(
            "/categories/<int:category_id>/edit",
            methods=["GET", "POST"],
        )(self.controller.edit_category)
        self.bp.route(
            "/categories/<int:category_id>/delete",
            methods=["POST"],
        )(self.controller.delete_category)
        self.bp.route("/skills", methods=["GET", "POST"])(self.controller.skills)
        return self.bp
