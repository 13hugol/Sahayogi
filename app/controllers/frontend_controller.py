from __future__ import annotations

from types import SimpleNamespace

from flask import abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from markupsafe import Markup, escape

from app.models import ProfileCertificate, ProfileReview, User

from .base_controller import BaseController


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
        return render_template("profile/edit.html", form=ProfileShellForm())

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
