from __future__ import annotations

from flask import flash, redirect, request, session, url_for
from flask_login import current_user
from markupsafe import Markup, escape

from app.auth import admin_required
from app.exceptions import InvalidRoleError, SelfRoleChangeError, UserNotFoundError
from app.services import AdminService
from app.validators import RoleAssignmentValidator

from .base_controller import BaseController


class AdminController(BaseController):
    def __init__(self, admin_service: AdminService, role_assignment_validator: RoleAssignmentValidator):
        self._admin_service = admin_service
        self._role_assignment_validator = role_assignment_validator

    @admin_required
    def dashboard(self):
        return self.render("admin/dashboard.html", stats=self._admin_service.dashboard_stats())

    @admin_required
    def users(self):
        target_id = request.args.get("user_id", type=int)
        users = self._admin_service.list_users()
        target_user = self._admin_service.find_user(target_id)
        return self.render("admin/users.html", users=users, target_user=target_user)

    @admin_required
    def update_user_role(self, user_id: int):
        new_role_name = request.form.get("role", "user")
        if self._role_assignment_validator.validate(new_role_name):
            flash("Invalid role.", "danger")
            return redirect(url_for("admin.users", user_id=user_id))

        try:
            target_user = self._admin_service.update_user_role(
                admin_user=current_user,
                target_user_id=user_id,
                new_role_name=new_role_name,
            )
        except UserNotFoundError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin.users"))
        except SelfRoleChangeError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin.users", user_id=user_id))
        except InvalidRoleError:
            flash("Invalid role.", "danger")
            return redirect(url_for("admin.users", user_id=user_id))

        normalized_role = str(new_role_name).strip().lower()
        flash(f"{target_user.full_name}'s role updated to '{normalized_role}'.", "success")
        return redirect(url_for("admin.users", user_id=target_user.id))

    @admin_required
    def listings(self):
        from app.models.skill import Category
        category_id = request.args.get("category_id", type=int)
        username = request.args.get("username", "").strip() or None
        sort_order = request.args.get("sort_order", "desc")
        
        listings = self._admin_service.get_pending_listings(
            category_id=category_id,
            username=username,
            sort_order=sort_order
        )
        categories = Category.all()
        return self.render(
            "admin/listings.html",
            listings=listings,
            categories=categories,
            category_id=category_id,
            username=username,
            sort_order=sort_order
        )

    @admin_required
    def approve_listing(self, listing_id: int):
        listing = self._admin_service.approve_listing(current_user, listing_id)
        if not listing:
            flash("Listing not found.", "danger")
            return redirect(url_for("admin.listings"))
        flash(f"Listing '{listing.title}' approved successfully.", "success")
        return redirect(url_for("admin.listings"))

    @admin_required
    def reject_listing(self, listing_id: int):
        reason = request.form.get("reason", "").strip()
        if not reason:
            flash("Rejection reason is required.", "danger")
            return redirect(url_for("admin.listings"))
            
        listing = self._admin_service.reject_listing(current_user, listing_id, reason)
        if not listing:
            flash("Listing not found.", "danger")
            return redirect(url_for("admin.listings"))
        
        from app.models.notification import Notification
        Notification.create(
            user_id=listing.user_id,
            message=f"Your skill listing '{listing.title}' was rejected. Reason: {reason}"
        )
        
        flash(f"Listing '{listing.title}' rejected.", "success")
        return redirect(url_for("admin.listings"))

    @admin_required
    def certificates(self):
        return self.render("admin/certificates.html", certificates=[])

    @admin_required
    def reports(self):
        reports_list = self._admin_service.list_reports()
        return self.render("admin/reports.html", reports=reports_list)

    @admin_required
    def resolve_report(self, report_id: int):
        decision = request.args.get("decision", "").strip()
        if decision not in {"resolved", "dismissed"}:
            flash("Invalid decision.", "danger")
            return redirect(url_for("admin.reports"))

        report = self._admin_service.resolve_report(current_user, report_id, decision)
        if not report:
            flash("Report not found.", "danger")
            return redirect(url_for("admin.reports"))

        flash(f"Report has been {decision}.", "success")
        return redirect(url_for("admin.reports"))

    @admin_required
    def reviews(self):
        return self.render("admin/reviews.html", reviews=[])

    @admin_required
    def categories(self):
        if request.method == "POST":
            flash("Category management is frontend-only in the current project scope.", "info")
        return self.render("admin/categories.html", categories=[], form=EmptyForm())

    @admin_required
    def edit_category(self, category_id: int):
        if request.method == "POST":
            flash("Category management is frontend-only in the current project scope.", "info")
        return self.render("admin/category_form.html", form=EmptyForm(), category=None)

    @admin_required
    def skills(self):
        if request.method == "POST":
            flash("Skill management is frontend-only in the current project scope.", "info")
        return self.render("admin/skills.html", skills=[], form=EmptyForm())


class EmptyForm:
    def hidden_tag(self):
        return Markup(f'<input type="hidden" name="csrf_token" value="{escape(session.get("csrf_token", ""))}">')

    def __getattr__(self, name):
        return EmptyField(name)


class EmptyField:
    def __init__(self, name: str):
        self.name = name
        self.label = EmptyLabel(name)

    def __call__(self, *args, **kwargs):
        attrs = _html_attrs(kwargs)
        if self.name == "description":
            return Markup(f'<textarea name="{self.name}" {attrs}></textarea>')
        if self.name == "category_id":
            return Markup(f'<select name="{self.name}" {attrs}></select>')
        if self.name == "submit":
            return Markup(f'<button type="submit" {attrs}>Save</button>')
        return Markup(f'<input type="text" name="{self.name}" {attrs}>')


class EmptyLabel:
    def __init__(self, name: str):
        self.name = name

    def __call__(self, *args, **kwargs):
        return Markup(f'<label { _html_attrs(kwargs) }>{escape(self.name.replace("_", " ").title())}</label>')


def _html_attrs(attrs: dict) -> str:
    normalized = []
    for key, value in attrs.items():
        if key.endswith("_"):
            key = key[:-1]
        key = key.replace("_", "-")
        if value is True:
            normalized.append(key)
        elif value not in {None, False}:
            normalized.append(f'{key}="{escape(str(value))}"')
    return " ".join(normalized)
