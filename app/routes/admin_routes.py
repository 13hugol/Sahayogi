from __future__ import annotations

from flask import Blueprint

from ..controllers.admin_controller import AdminController


class AdminRoutes:
    def __init__(self):
        self.bp = Blueprint("admin", __name__, url_prefix="/admin")
        self.controller = AdminController()

    def register(self):
        self.bp.route("/")(self.controller.dashboard)
        self.bp.route("/users")(self.controller.users)
        self.bp.route("/users/<int:user_id>/role", methods=["POST"])(self.controller.update_user_role)
        self.bp.route("/listings")(self.controller.listings)
        self.bp.route("/certificates")(self.controller.certificates)
        self.bp.route("/reports")(self.controller.reports)
        self.bp.route("/reviews")(self.controller.reviews)
        self.bp.route("/categories", methods=["GET", "POST"])(self.controller.categories)
        self.bp.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])(self.controller.edit_category)
        self.bp.route("/skills", methods=["GET", "POST"])(self.controller.skills)
        return self.bp
