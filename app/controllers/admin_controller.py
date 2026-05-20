from __future__ import annotations

from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user
from markupsafe import Markup, escape

from app.auth import admin_required
from app.models import AdminAuditLog, Role, User
from .base_controller import BaseController


class AdminController(BaseController):
    @admin_required
    def dashboard(self):
        stats = {
            "total_users": User.count(),
            "admin_users": Role.count_by_name("admin"),
            "regular_users": Role.count_by_name("user"),
            "verified_users": User.verified_count(),
            "audit_logs": AdminAuditLog.count(),
        }
        return render_template("admin/dashboard.html", stats=stats)

    @admin_required
    def users(self):
        target_id = request.args.get("user_id", type=int)
        users = User.all()
        target_user = User.find_by_id(target_id) if target_id else None
        return render_template("admin/users.html", users=users, target_user=target_user)

    @admin_required
    def update_user_role(self, user_id: int):
        target_user = User.find_by_id(user_id)
        if not target_user:
            flash("User not found.", "danger")
            return redirect(url_for("admin.users"))
        if target_user.id == current_user.id:
            flash("You cannot change your own role.", "danger")
            return redirect(url_for("admin.users", user_id=target_user.id))

        new_role_name = request.form.get("role", "user")
        if new_role_name not in {"user", "admin"}:
            flash("Invalid role.", "danger")
            return redirect(url_for("admin.users", user_id=target_user.id))

        old_role_name = target_user.role.name if target_user.role else "unknown"
        new_role = Role.ensure(
            new_role_name,
            "Administrator" if new_role_name == "admin" else "Platform member",
        )
        target_user.update_role(new_role)
        AdminAuditLog.create(
            admin_id=current_user.id,
            action="update_user_role",
            target_type="User",
            target_id=target_user.id,
            detail=f"Role changed from '{old_role_name}' to '{new_role_name}' by admin {current_user.email}",
        )
        flash(f"{target_user.full_name}'s role updated to '{new_role_name}'.", "success")
        return redirect(url_for("admin.users", user_id=target_user.id))

    @admin_required
    def listings(self):
        return render_template("admin/listings.html", listings=[])

    @admin_required
    def certificates(self):
        return render_template("admin/certificates.html", certificates=[])

    @admin_required
    def reports(self):
        return render_template("admin/reports.html", reports=[])

    @admin_required
    def reviews(self):
        return render_template("admin/reviews.html", reviews=[])

    @admin_required
    def categories(self):
        if request.method == "POST":
            flash("Category management is frontend-only in the current project scope.", "info")
        return render_template("admin/categories.html", categories=[], form=EmptyForm())

    @admin_required
    def edit_category(self, category_id: int):
        if request.method == "POST":
            flash("Category management is frontend-only in the current project scope.", "info")
        return render_template("admin/category_form.html", form=EmptyForm(), category=None)

    @admin_required
    def skills(self):
        if request.method == "POST":
            flash("Skill management is frontend-only in the current project scope.", "info")
        return render_template("admin/skills.html", skills=[], form=EmptyForm())


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
