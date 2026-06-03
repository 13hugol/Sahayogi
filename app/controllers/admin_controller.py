from __future__ import annotations

import re

from flask import flash, redirect, request, session, url_for
from flask_login import current_user
from markupsafe import Markup, escape

from app.auth import admin_required
from app.exceptions import CategoryNotFoundError, InvalidRoleError, SelfRoleChangeError, UserNotFoundError
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
        return self.render("admin/listings.html", listings=[])

    @admin_required
    def certificates(self):
        return self.render("admin/certificates.html", certificates=[])

    @admin_required
    def reports(self):
        return self.render("admin/reports.html", reports=[])

    @admin_required
    def reviews(self):
        return self.render("admin/reviews.html", reviews=[])

    @admin_required
    def categories(self):
        form = CategoryForm(submit_label="Create category")
        if request.method == "POST":
            form = CategoryForm(request.form, submit_label="Create category")
            if form.validate(self._admin_service):
                category = self._admin_service.create_category(
                    admin_user=current_user,
                    **form.cleaned,
                )
                flash(f"Category {category.name} created.", "success")
                return redirect(url_for("admin.categories"))
        return self.render("admin/categories.html", categories=self._admin_service.list_categories(), form=form)

    @admin_required
    def edit_category(self, category_id: int):
        category = self._admin_service.find_category(category_id)
        if not category:
            flash("Category not found.", "danger")
            return redirect(url_for("admin.categories"))

        form = CategoryForm(category=category, submit_label="Save category")
        if request.method == "POST":
            form = CategoryForm(request.form, category=category, submit_label="Save category")
            if form.validate(self._admin_service, exclude_id=category.id):
                try:
                    category = self._admin_service.update_category(
                        admin_user=current_user,
                        category_id=category.id,
                        **form.cleaned,
                    )
                except CategoryNotFoundError:
                    flash("Category not found.", "danger")
                    return redirect(url_for("admin.categories"))
                flash(f"Category {category.name} updated.", "success")
                return redirect(url_for("admin.categories"))
        return self.render("admin/category_form.html", form=form, category=category)

    @admin_required
    def skills(self):
        if request.method == "POST":
            flash("Skill management is frontend-only in the current project scope.", "info")
        return self.render("admin/skills.html", skills=[], form=EmptyForm())


class CategoryForm:
    def __init__(self, form_data=None, *, category=None, submit_label: str = "Save category"):
        self.errors: dict[str, str] = {}
        self.cleaned: dict[str, str] = {}
        self.submit_label = submit_label
        self.values = {
            "name": self._initial_value("name", form_data, category),
            "slug": self._initial_value("slug", form_data, category),
            "icon": self._initial_value("icon", form_data, category),
            "description": self._initial_value("description", form_data, category),
        }

    def hidden_tag(self):
        return Markup(f'<input type="hidden" name="csrf_token" value="{escape(session.get("csrf_token", ""))}">')

    def validate(self, admin_service: AdminService, *, exclude_id: int | None = None) -> bool:
        self.errors = {}
        name = normalize_spaces(self.values.get("name", ""))
        slug = slugify(self.values.get("slug", "") or name)
        icon = normalize_icon(self.values.get("icon", "") or name)
        description = normalize_spaces(self.values.get("description", ""))

        if not name:
            self.errors["name"] = "Category name is required."
        elif len(name) > 80:
            self.errors["name"] = "Category name must be 80 characters or fewer."
        elif admin_service.category_name_exists(name, exclude_id=exclude_id):
            self.errors["name"] = "A category with this name already exists."

        if not slug:
            self.errors["slug"] = "Slug is required."
        elif len(slug) > 100:
            self.errors["slug"] = "Slug must be 100 characters or fewer."
        elif admin_service.category_slug_exists(slug, exclude_id=exclude_id):
            self.errors["slug"] = "A category with this slug already exists."

        if len(icon) > 16:
            self.errors["icon"] = "Label must be 16 characters or fewer."

        if len(description) > 255:
            self.errors["description"] = "Description must be 255 characters or fewer."

        self.values.update(
            {
                "name": name,
                "slug": slug,
                "icon": icon,
                "description": description,
            }
        )
        self.cleaned = {
            "name": name,
            "slug": slug,
            "icon": icon,
            "description": description,
        }
        return not self.errors

    def __getattr__(self, name: str):
        if name == "submit":
            return CategoryField(name, self.submit_label, self.submit_label, {})
        return CategoryField(name, self.values.get(name, ""), name.replace("_", " ").title(), self.errors)

    @staticmethod
    def _initial_value(name: str, form_data, category) -> str:
        if form_data is not None:
            return str(form_data.get(name, ""))
        return str(getattr(category, name, "") or "")


class CategoryField:
    def __init__(self, name: str, value: str, label: str, errors: dict[str, str]):
        self.name = name
        self.value = value
        self.errors = [errors[name]] if name in errors else []
        self.label = CategoryLabel(label, name)

    def __call__(self, *args, **kwargs):
        error_class = " is-invalid" if self.errors else ""
        if self.name == "description":
            attrs_with_class = dict(kwargs)
            attrs_with_class.setdefault("id", self.name)
            css_class = str(attrs_with_class.get("class", ""))
            attrs_with_class["class"] = f"{css_class}{error_class}"
            return Markup(
                f'<textarea name="{self.name}" {_html_attrs(attrs_with_class)}>'
                f"{escape(self.value)}</textarea>"
            )
        if self.name == "submit":
            attrs = _html_attrs(kwargs)
            return Markup(f'<button type="submit" {attrs}>{escape(self.value)}</button>')

        attrs_with_value = dict(kwargs)
        attrs_with_value.setdefault("id", self.name)
        attrs_with_value["value"] = self.value
        css_class = str(attrs_with_value.get("class", ""))
        attrs_with_value["class"] = f"{css_class}{error_class}"
        return Markup(f'<input type="text" name="{self.name}" {_html_attrs(attrs_with_value)}>')


class CategoryLabel:
    def __init__(self, text: str, field_name: str):
        self.text = text
        self.field_name = field_name

    def __call__(self, *args, **kwargs):
        attrs = {"for": self.field_name, **kwargs}
        return Markup(f'<label {_html_attrs(attrs)}>{escape(self.text)}</label>')


def normalize_spaces(value: str) -> str:
    return " ".join(str(value or "").split())


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())
    return slug.strip("-")


def normalize_icon(value: str) -> str:
    compact = re.sub(r"[^A-Za-z0-9]+", "", str(value or ""))
    if compact:
        return compact[:16].upper()
    words = [word[:1] for word in normalize_spaces(value).split() if word]
    return "".join(words).upper()[:16] or "CAT"


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
