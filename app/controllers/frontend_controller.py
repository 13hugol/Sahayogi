from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from markupsafe import Markup, escape
from werkzeug.utils import secure_filename

from app.models import Profile, ProfileCertificate, ProfileReview, ProfileSkill, User

from .base_controller import BaseController

MAX_AVATAR_BYTES = 5 * 1024 * 1024
ALLOWED_AVATAR_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_AVATAR_MIMETYPES = {"image/jpeg", "image/png"}


class FrontendController(BaseController):
    def _categories(self):
        return [
            SimpleNamespace(id=1, name="Tech"),
            SimpleNamespace(id=2, name="Music"),
            SimpleNamespace(id=3, name="Language"),
            SimpleNamespace(id=4, name="Kitchen"),
        ]

    def marketplace(self):
        return render_template(
            "listings/index.html",
            listings=[],
            categories=self._categories(),
            page=1,
            total_pages=1,
            total_results=0,
        )

    @login_required
    def post_listing(self):
        return render_template("listings/form.html", form=ListingShellForm(), title="Create listing")

    @login_required
    def my_listings(self):
        return render_template("listings/mine.html", listings=[])

    def listing_detail(self, listing_id: int):
        listing = SimpleNamespace(
            id=listing_id,
            title="Skill listing preview",
            description="This frontend page is available, but listing persistence is not active in the backend scope.",
            exchange_type="credit",
            min_credits=10,
            location_text="Kathmandu or remote",
            contact_method="Platform messaging",
            status="frontend-only",
            availability=[],
            skill=SimpleNamespace(name="Python"),
            category=SimpleNamespace(name="Tech"),
            user=SimpleNamespace(
                id=0,
                full_name="Sahayogi Member",
                profile=SimpleNamespace(location="Kathmandu", reputation_score=0, contact_email=None),
                has_verified_skill=lambda _skill_id: False,
            ),
            skill_id=1,
            user_id=0,
        )
        return render_template("listings/detail.html", listing=listing, request_form=RequestShellForm())

    def api_search(self):
        html = render_template("partials/listing_cards.html", listings=[])
        return jsonify({"count": 0, "html": html})

    @login_required
    def wallet(self):
        return render_template("credits/ledger.html", entries=[], holds=[])

    @login_required
    def matches(self):
        return render_template("matches/index.html", matches=[])

    @login_required
    def requests(self):
        return render_template("requests/inbox.html", requests=[])

    @login_required
    def sent_requests(self):
        return render_template("requests/sent.html", requests=[])

    @login_required
    def exchanges(self):
        return render_template("exchanges/index.html", exchanges=[])

    @login_required
    def exchange_detail(self, exchange_id: int):
        exchange = SimpleNamespace(
            id=exchange_id,
            status="frontend-only",
            exchange_type="credit",
            created_at=None,
            completed_at=None,
            request=SimpleNamespace(credits_reserved=0),
            barter_skill=None,
            listing=SimpleNamespace(title="Exchange preview"),
            teacher=SimpleNamespace(full_name="Teacher"),
            learner=SimpleNamespace(full_name="Learner"),
            conversation=None,
            completion_marks=[],
        )
        return render_template(
            "exchanges/detail.html",
            exchange=exchange,
            can_mark_complete=False,
            can_review=False,
            reviews=[],
        )

    @login_required
    def messages(self):
        return render_template("messages/index.html", conversations=[])

    @login_required
    def conversation(self, conversation_id: int):
        conversation = SimpleNamespace(
            id=conversation_id,
            subject="Conversation preview",
            messages=[],
            other_participant=lambda _user_id: SimpleNamespace(full_name="Exchange partner"),
        )
        return render_template("messages/detail.html", conversation=conversation, form=MessageShellForm())

    @login_required
    def notifications(self):
        return render_template("notifications/index.html", notifications=[])

    @login_required
    def notification_counts(self):
        return jsonify({"messages": 0, "notifications": 0})

    @login_required
    def profile_me(self):
        return self.profile_view(current_user.id)

    @login_required
    def profile_edit(self):
        user = User.find_by_id(current_user.id)
        if not user or not user.profile:
            abort(404)

        errors: dict[str, str] = {}
        values = self._profile_edit_values(user)

        if request.method == "POST":
            values = self._submitted_profile_values()
            errors = self._validate_profile_edit(values)
            avatar = request.files.get("avatar")
            avatar_extension = None

            if avatar and avatar.filename:
                avatar_extension, avatar_error = self._validate_avatar_upload(avatar)
                if avatar_error:
                    errors["avatar"] = avatar_error

            if not errors:
                avatar_path = None
                if avatar and avatar.filename and avatar_extension:
                    avatar_path = self._save_avatar_upload(avatar, avatar_extension)

                User.update_full_name(user.id, values["full_name"])
                Profile.update_details(
                    user.id,
                    location=values["location"],
                    bio=values["bio"],
                    avatar_path=avatar_path,
                )
                ProfileSkill.sync_for_user(user.id, "offered", values["offered_skills"])
                ProfileSkill.sync_for_user(user.id, "wanted", values["wanted_skills"])
                flash("Profile updated successfully.", "success")
                return redirect(url_for("profile.edit"))

        return render_template(
            "profile/edit.html",
            errors=errors,
            max_avatar_mb=5,
            user=user,
            values=values,
        )

    def _profile_edit_values(self, user: User) -> dict:
        return {
            "full_name": user.full_name,
            "bio": user.profile.bio or "",
            "location": user.profile.location or "",
            "offered_skills": [skill.skill_name for skill in user.offered_skills],
            "wanted_skills": [skill.skill_name for skill in user.wanted_skills],
        }

    def _submitted_profile_values(self) -> dict:
        return {
            "full_name": request.form.get("full_name", "").strip(),
            "bio": request.form.get("bio", "").strip(),
            "location": request.form.get("location", "").strip(),
            "offered_skills": ProfileSkill.clean_skill_names(request.form.getlist("offered_skills")),
            "wanted_skills": ProfileSkill.clean_skill_names(request.form.getlist("wanted_skills")),
        }

    def _validate_profile_edit(self, values: dict) -> dict[str, str]:
        errors: dict[str, str] = {}
        if not values["full_name"]:
            errors["full_name"] = "Full name is required."
        elif len(values["full_name"]) > 120:
            errors["full_name"] = "Full name must be 120 characters or fewer."

        if not values["location"]:
            errors["location"] = "Location is required."
        elif len(values["location"]) > 160:
            errors["location"] = "Location must be 160 characters or fewer."

        if len(values["bio"]) > 1000:
            errors["bio"] = "Bio must be 1000 characters or fewer."

        for field_name in ("offered_skills", "wanted_skills"):
            if any(len(skill_name) > 120 for skill_name in values[field_name]):
                errors[field_name] = "Each skill must be 120 characters or fewer."

        return errors

    def _validate_avatar_upload(self, avatar) -> tuple[str | None, str | None]:
        filename = secure_filename(avatar.filename or "")
        extension = Path(filename).suffix.lower()
        if extension not in ALLOWED_AVATAR_EXTENSIONS:
            return None, "Avatar must be a JPG or PNG file."
        if avatar.mimetype not in ALLOWED_AVATAR_MIMETYPES:
            return None, "Avatar must be uploaded as a JPG or PNG image."

        try:
            avatar.stream.seek(0, os.SEEK_END)
            size = avatar.stream.tell()
            avatar.stream.seek(0)
            header = avatar.stream.read(16)
            avatar.stream.seek(0)
        except OSError:
            return None, "Avatar could not be read. Please choose another file."

        if size <= 0:
            return None, "Avatar file is empty."
        if size > MAX_AVATAR_BYTES:
            return None, "Avatar must be under 5MB."
        if extension == ".png" and not header.startswith(b"\x89PNG\r\n\x1a\n"):
            return None, "Avatar file content must match the PNG format."
        if extension in {".jpg", ".jpeg"} and not header.startswith(b"\xff\xd8\xff"):
            return None, "Avatar file content must match the JPG format."

        return extension, None

    def _save_avatar_upload(self, avatar, extension: str) -> str:
        avatar_dir = Path(current_app.config["UPLOAD_FOLDER"]) / "avatars"
        avatar_dir.mkdir(parents=True, exist_ok=True)
        filename = f"user-{current_user.id}-{uuid4().hex}{extension}"
        avatar.stream.seek(0)
        avatar.save(avatar_dir / filename)
        return f"avatars/{filename}"

    @login_required
    def certificates(self):
        return render_template("profile/certificates.html", form=CertificateShellForm(), certificates=[])

    def profile_view(self, user_id: int):
        user = User.find_by_id(user_id)
        if not user or not user.profile:
            abort(404)
        return render_template(
            "profile/view.html",
            user=user,
            approved_listings=[],
            approved_certificates=ProfileCertificate.approved_for_user(user.id),
            recent_reviews=ProfileReview.recent_for_user(user.id),
            report_form=ReportShellForm(),
        )

    def report_user(self, user_id: int):
        return self.profile_view(user_id)

    def top_rated(self):
        return render_template("reviews/top_rated.html", profiles=[])

    def user_reviews(self, user_id: int):
        return render_template("reviews/user_reviews.html", review_user=shell_user(user_id), reviews=[])

    @login_required
    def review_form(self, exchange_id: int):
        exchange = SimpleNamespace(id=exchange_id, listing=SimpleNamespace(title="Exchange preview"))
        reviewee = SimpleNamespace(full_name="Exchange partner")
        return render_template("reviews/form.html", form=ReviewShellForm(), exchange=exchange, reviewee=reviewee)

    def frontend_only_action(self, *args, **kwargs):
        flash("This action is frontend-only in the current project scope.", "info")
        return redirect(request.referrer or url_for("main.dashboard"))


def shell_user(user_id: int):
    return SimpleNamespace(
        id=user_id,
        full_name="Sahayogi Member",
        email="member@example.com",
        role=SimpleNamespace(name="user"),
        offered_skills=[],
        wanted_skills=[],
        profile=SimpleNamespace(
            avatar_path=None,
            username=f"member{user_id}",
            headline="Skill exchange member",
            location="Kathmandu",
            reputation_score=0,
            completed_exchange_count=0,
            bio="Frontend-only profile preview.",
            contact_email=None,
        ),
    )


class ShellForm:
    fields: dict[str, str] = {}

    def hidden_tag(self):
        token = session.get("csrf_token", "")
        return Markup(f'<input type="hidden" name="csrf_token" value="{escape(token)}">')

    def __getattr__(self, name: str):
        field_type = self.fields.get(name, "text")
        return ShellField(name, field_type)


class ShellField:
    def __init__(self, name: str, field_type: str = "text"):
        self.name = name
        self.field_type = field_type
        self.errors = []
        self.label = ShellLabel(name)

    def __call__(self, *args, **kwargs):
        attrs = html_attrs(kwargs)
        if self.field_type == "textarea":
            return Markup(f'<textarea name="{self.name}" {attrs}></textarea>')
        if self.field_type == "select":
            return Markup(f'<select name="{self.name}" {attrs}></select>')
        if self.field_type == "submit":
            return Markup(f'<button type="submit" {attrs}>Save</button>')
        return Markup(f'<input type="{self.field_type}" name="{self.name}" {attrs}>')

    def __iter__(self):
        if self.name == "exchange_type":
            yield ShellRadioField(self.name, "credit", "Credit")
            yield ShellRadioField(self.name, "teach", "Teach")
        return


class ShellRadioField:
    def __init__(self, name: str, value: str, label: str):
        self.name = name
        self.value = value
        self.label = ShellTextLabel(label)

    def __call__(self, *args, **kwargs):
        attrs = html_attrs(kwargs)
        return Markup(f'<input type="radio" name="{self.name}" value="{self.value}" {attrs}>')


class ShellLabel:
    def __init__(self, name: str):
        self.name = name

    def __call__(self, *args, **kwargs):
        return Markup(f'<label for="{self.name}" {html_attrs(kwargs)}>{escape(self.name.replace("_", " ").title())}</label>')


class ShellTextLabel:
    def __init__(self, text: str):
        self.text = text

    def __call__(self, *args, **kwargs):
        return Markup(f'<label {html_attrs(kwargs)}>{escape(self.text)}</label>')


class ListingShellForm(ShellForm):
    fields = {
        "description": "textarea",
        "availability_labels": "textarea",
        "exchange_type": "select",
        "skill_id": "select",
        "category_id": "select",
        "submit": "submit",
    }


class RequestShellForm(ShellForm):
    fields = {"offered_skill_id": "select", "requested_message": "textarea", "submit": "submit"}


class ProfileShellForm(ShellForm):
    fields = {
        "bio": "textarea",
        "offered_skills": "select",
        "wanted_skills": "select",
        "avatar": "file",
        "submit": "submit",
    }


class CertificateShellForm(ShellForm):
    fields = {"skill_id": "select", "certificate": "file", "submit": "submit"}


class MessageShellForm(ShellForm):
    fields = {"body": "textarea", "submit": "submit"}


class ReportShellForm(ShellForm):
    fields = {"reason": "select", "description": "textarea", "submit": "submit"}


class ReviewShellForm(ShellForm):
    fields = {"rating": "select", "comment": "textarea", "submit": "submit"}


def html_attrs(attrs: dict) -> str:
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
