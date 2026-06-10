from __future__ import annotations

from flask import abort, flash, redirect, request, session, url_for
from flask_login import current_user
from markupsafe import Markup, escape

from app.auth import admin_required
from app.exceptions import (
    CategoryInUseError,
    CategoryNotFoundError,
    DuplicateCategoryError,
    InvalidRoleError,
    SelfRoleChangeError,
    UserNotFoundError,
)
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
        self._admin_service._notification_service.notify_listing_approved(
            user_id=listing.user_id,
            skill_title=listing.title,
            target_url="/listings/mine",
        )
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

        self._admin_service._notification_service.notify_listing_rejected(
            user_id=listing.user_id,
            skill_title=listing.title,
            reason=reason,
            target_url="/listings/mine",
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
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip() or None
            icon = (request.form.get("icon", "CAT") or "CAT").strip().upper()[:8] or "CAT"
            try:
                sort_order = int(request.form.get("sort_order", "0") or 0)
            except ValueError:
                sort_order = 0
            try:
                self._admin_service.create_category(
                    admin_user=current_user,
                    name=name,
                    description=description,
                    icon=icon,
                    sort_order=sort_order,
                )
            except DuplicateCategoryError as exc:
                flash(str(exc), "danger")
            except ValueError as exc:
                flash(str(exc), "danger")
            else:
                flash(f"Category '{name}' created.", "success")
            return redirect(url_for("admin.categories"))

        categories = self._admin_service.list_categories()
        return self.render("admin/categories.html", categories=categories, form=EmptyForm())

    @admin_required
    def edit_category(self, category_id: int):
        category = self._admin_service.find_category(category_id)
        if not category:
            abort(404)
        if request.method == "POST":
            name = request.form.get("name", "").strip() or category.name
            description = request.form.get("description", "").strip() or None
            icon_raw = request.form.get("icon", category.icon or "CAT").strip().upper()[:8]
            icon = icon_raw or "CAT"
            try:
                sort_order = int(request.form.get("sort_order", str(category.sort_order)) or 0)
            except ValueError:
                sort_order = category.sort_order
            is_active = request.form.get("is_active") == "on"
            try:
                self._admin_service.update_category(
                    admin_user=current_user,
                    category_id=category_id,
                    name=name,
                    description=description,
                    icon=icon,
                    sort_order=sort_order,
                    is_active=is_active,
                )
            except CategoryNotFoundError:
                abort(404)
            flash(f"Category '{name}' updated.", "success")
            return redirect(url_for("admin.categories"))

        return self.render("admin/category_form.html", form=EmptyForm(), category=category)

    @admin_required
    def delete_category(self, category_id: int):
        try:
            self._admin_service.delete_category(current_user, category_id)
        except CategoryNotFoundError:
            abort(404)
        except CategoryInUseError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin.categories"))
        flash("Category removed.", "success")
        return redirect(url_for("admin.categories"))

    @admin_required
    def skills(self):
        if request.method == "POST":
            flash("Skill management is frontend-only in the current project scope.", "info")
        return self.render("admin/skills.html", skills=[], form=EmptyForm())

    @admin_required
    def suspend_user(self, user_id: int):
        try:
            days = int(request.form.get("days", "0"))
            reason = request.form.get("reason", "").strip()
            self._admin_service.suspend_user(
                admin_user=current_user,
                target_user_id=user_id,
                days=days,
                reason=reason,
            )
            flash("User has been temporarily suspended.", "success")
        except ValueError as exc:
            flash(str(exc), "danger")
        except UserNotFoundError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin.users"))
            
        return redirect(url_for("admin.users", user_id=user_id))

    @admin_required
    def ban_user(self, user_id: int):
        try:
            reason = request.form.get("reason", "").strip()
            self._admin_service.ban_user(
                admin_user=current_user,
                target_user_id=user_id,
                reason=reason,
            )
            flash("User has been permanently banned and their active listings deactivated.", "success")
        except ValueError as exc:
            flash(str(exc), "danger")
        except UserNotFoundError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin.users"))
            
        return redirect(url_for("admin.users", user_id=user_id))

    @admin_required
    def unsuspend_user(self, user_id: int):
        try:
            self._admin_service.unsuspend_user(
                admin_user=current_user,
                target_user_id=user_id,
            )
            flash("User restriction has been lifted.", "success")
        except UserNotFoundError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin.users"))
            
        return redirect(url_for("admin.users", user_id=user_id))


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
