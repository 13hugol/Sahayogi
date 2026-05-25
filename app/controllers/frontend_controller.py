from __future__ import annotations

from types import SimpleNamespace

from flask import abort, flash, jsonify, redirect, request, session, url_for
from flask_login import current_user, login_required
from markupsafe import Markup, escape

from app.exceptions import ProfileNotFoundError
from app.services import ProfileService, SkillService

from .base_controller import BaseController


class FrontendController(BaseController):
    def __init__(self, profile_service: ProfileService, skill_service: SkillService):
        self._profile_service = profile_service
        self._skill_service = skill_service

    def marketplace(self):
        q = request.args.get("q", "").strip()
        categories = self._skill_service.get_all_categories()
        
        listings = self._skill_service.search_listings(query=q if q else None, status="approved")
        
        category_ids = [int(cid) for cid in request.args.getlist("category") if cid.isdigit()]
        if category_ids:
            listings = [l for l in listings if l.category_id in category_ids]
            
        page = request.args.get("page", 1, type=int)
        per_page = 6
        total_results = len(listings)
        total_pages = max(1, (total_results + per_page - 1) // per_page)
        
        start = (page - 1) * per_page
        end = start + per_page
        paginated_listings = listings[start:end]
        
        return self.render(
            "listings/index.html",
            listings=paginated_listings,
            categories=categories,
            page=page,
            total_pages=total_pages,
            total_results=total_results,
        )

    @login_required
    def post_listing(self, listing_id: int = None):
        is_edit = listing_id is not None
        title_text = "Edit listing" if is_edit else "Create listing"
        
        listing = None
        if is_edit:
            listing = self._skill_service.get_listing_by_id(listing_id)
            if not listing:
                abort(404)
            if listing.user_id != current_user.id:
                abort(403)
                
        skill_choices = [(ps.id, ps.skill_name) for ps in current_user.offered_skills]
        categories = self._skill_service.get_all_categories()
        category_choices = [(c.id, c.name) for c in categories]
        
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            exchange_type = request.form.get("exchange_type", "").strip()
            skill_id_str = request.form.get("skill_id", "").strip()
            category_id_str = request.form.get("category_id", "").strip()
            description = request.form.get("description", "").strip()
            min_credits_str = request.form.get("min_credits", "10").strip()
            location_text = request.form.get("location_text", "").strip()
            contact_method = request.form.get("contact_method", "").strip()
            availability_labels = request.form.get("availability_labels", "").strip()
            
            form = ListingShellForm(
                data={
                    "title": title,
                    "description": description,
                    "exchange_type": exchange_type,
                    "skill_id": skill_id_str,
                    "category_id": category_id_str,
                    "min_credits": min_credits_str,
                    "location_text": location_text,
                    "contact_method": contact_method,
                    "availability_labels": availability_labels,
                }
            )
            form.skill_id.choices = skill_choices
            form.category_id.choices = category_choices
            
            if not title or len(title) < 5 or len(title) > 120:
                form.title.errors.append("Title must be between 5 and 120 characters.")
            if not description or len(description) < 10:
                form.description.errors.append("Description must be at least 10 characters.")
            
            skill_id = None
            try:
                skill_id = int(skill_id_str)
                if skill_id not in [ps.id for ps in current_user.offered_skills]:
                    form.skill_id.errors.append("Please select a valid skill from your profile.")
            except ValueError:
                form.skill_id.errors.append("Please select a valid skill.")
                
            category_id = None
            try:
                category_id = int(category_id_str)
                if not self._skill_service.get_category_by_id(category_id):
                    form.category_id.errors.append("Please select a valid category.")
            except ValueError:
                form.category_id.errors.append("Please select a valid category.")
                
            if exchange_type not in ["credit", "teach"]:
                form.exchange_type.errors.append("Please select a valid exchange type.")
                
            credit_cost = 10
            if exchange_type == "credit":
                try:
                    credit_cost = int(min_credits_str)
                    if credit_cost < 0:
                        form.min_credits.errors.append("Credits cannot be negative.")
                except ValueError:
                    form.min_credits.errors.append("Please enter a valid number of credits.")
            else:
                credit_cost = 0
            
            if not availability_labels:
                form.availability_labels.errors.append("Please provide availability details.")
                
            has_errors = False
            all_fields = set(form.fields.keys()) | set(form._fields_cache.keys())
            for field_name in all_fields:
                field = getattr(form, field_name)
                if field.errors:
                    has_errors = True
                    for err in field.errors:
                        flash(err, "danger")
                
            if not has_errors:
                if is_edit:
                    self._skill_service.edit_listing(
                        listing_id=listing_id,
                        category_id=category_id,
                        skill_id=skill_id,
                        title=title,
                        description=description,
                        exchange_type=exchange_type,
                        credit_cost=credit_cost,
                        availability=availability_labels,
                        location_text=location_text,
                        contact_method=contact_method,
                        status="pending"
                    )
                    flash("Listing updated successfully and is pending admin review.", "success")
                else:
                    self._skill_service.create_listing(
                        user_id=current_user.id,
                        category_id=category_id,
                        skill_id=skill_id,
                        title=title,
                        description=description,
                        exchange_type=exchange_type,
                        credit_cost=credit_cost,
                        availability=availability_labels,
                        location_text=location_text,
                        contact_method=contact_method,
                        status="pending"
                    )
                    flash("Listing submitted successfully and is pending admin review.", "success")
                return redirect(url_for("listings.mine"))
        else:
            if is_edit:
                availability_str = "\n".join([item.label for item in listing.availability])
                form = ListingShellForm(
                    data={
                        "title": listing.title,
                        "description": listing.description,
                        "exchange_type": listing.exchange_type,
                        "skill_id": listing.skill_id,
                        "category_id": listing.category_id,
                        "min_credits": listing.credit_cost,
                        "location_text": listing.location_text,
                        "contact_method": listing.contact_method,
                        "availability_labels": availability_str,
                    }
                )
            else:
                form = ListingShellForm(
                    data={
                        "exchange_type": "credit",
                        "min_credits": 10,
                    }
                )
            form.skill_id.choices = skill_choices
            form.category_id.choices = category_choices
            
        return self.render("listings/form.html", form=form, title=title_text)

    @login_required
    def my_listings(self):
        listings = self._skill_service.get_listings_by_user(current_user.id)
        return self.render("listings/mine.html", listings=listings)

    def listing_detail(self, listing_id: int):
        listing = self._skill_service.get_listing_by_id(listing_id)
        if not listing:
            abort(404)
        return self.render("listings/detail.html", listing=listing, request_form=RequestShellForm())

    def api_search(self):
        q = request.args.get("q", "").strip()
        listings = self._skill_service.search_listings(query=q if q else None, status="approved")
        category_ids = [int(cid) for cid in request.args.getlist("category") if cid.isdigit()]
        if category_ids:
            listings = [l for l in listings if l.category_id in category_ids]
            
        page = request.args.get("page", 1, type=int)
        per_page = 6
        total_results = len(listings)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_listings = listings[start:end]
        
        html = self.render("partials/listing_cards.html", listings=paginated_listings)
        return jsonify({"count": total_results, "html": html})

    @login_required
    def delete_listing(self, listing_id: int):
        listing = self._skill_service.get_listing_by_id(listing_id)
        if not listing:
            abort(404)
        if listing.user_id != current_user.id:
            abort(403)
        self._skill_service.delete_listing(listing_id)
        flash("Listing deleted successfully.", "success")
        return redirect(url_for("listings.mine"))

    @login_required
    def wallet(self):
        return self.render("credits/ledger.html", entries=[], holds=[])

    @login_required
    def matches(self):
        return self.render("matches/index.html", matches=[])

    @login_required
    def requests(self):
        return self.render("requests/inbox.html", requests=[])

    @login_required
    def sent_requests(self):
        return self.render("requests/sent.html", requests=[])

    @login_required
    def exchanges(self):
        return self.render("exchanges/index.html", exchanges=[])

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
        return self.render(
            "exchanges/detail.html",
            exchange=exchange,
            can_mark_complete=False,
            can_review=False,
            reviews=[],
        )

    @login_required
    def messages(self):
        return self.render("messages/index.html", conversations=[])

    @login_required
    def conversation(self, conversation_id: int):
        conversation = SimpleNamespace(
            id=conversation_id,
            subject="Conversation preview",
            messages=[],
            other_participant=lambda _user_id: SimpleNamespace(full_name="Exchange partner"),
        )
        return self.render("messages/detail.html", conversation=conversation, form=MessageShellForm())

    @login_required
    def notifications(self):
        return self.render("notifications/index.html", notifications=[])

    @login_required
    def notification_counts(self):
        return jsonify({"messages": 0, "notifications": 0})

    @login_required
    def profile_me(self):
        return self.profile_view(current_user.id)

    @login_required
    def profile_edit(self):
        return self.render("profile/edit.html", form=ProfileShellForm())

    @login_required
    def certificates(self):
        return self.render("profile/certificates.html", form=CertificateShellForm(), certificates=[])

    def profile_view(self, user_id: int):
        try:
            page_data = self._profile_service.get_profile_page_data(user_id)
        except ProfileNotFoundError:
            abort(404)
        return self.render(
            "profile/view.html",
            user=page_data.user,
            approved_listings=page_data.approved_listings,
            approved_certificates=page_data.approved_certificates,
            recent_reviews=page_data.recent_reviews,
            report_form=ReportShellForm(),
        )

    def report_user(self, user_id: int):
        return self.profile_view(user_id)

    def top_rated(self):
        return self.render("reviews/top_rated.html", profiles=self._profile_service.get_top_rated_profiles())

    def user_reviews(self, user_id: int):
        try:
            review_user, reviews = self._profile_service.get_review_history(user_id)
        except ProfileNotFoundError:
            abort(404)
        return self.render("reviews/user_reviews.html", review_user=review_user, reviews=reviews)

    @login_required
    def review_form(self, exchange_id: int):
        exchange = SimpleNamespace(id=exchange_id, listing=SimpleNamespace(title="Exchange preview"))
        reviewee = SimpleNamespace(full_name="Exchange partner")
        return self.render("reviews/form.html", form=ReviewShellForm(), exchange=exchange, reviewee=reviewee)

    def frontend_only_action(self, *args, **kwargs):
        flash("This action is frontend-only in the current project scope.", "info")
        return redirect(request.referrer or url_for("main.dashboard"))


class ShellForm:
    fields: dict[str, str] = {}

    def __init__(self, data=None, **kwargs):
        self._fields_cache = {}
        self.data_dict = {}
        if data:
            if isinstance(data, dict):
                self.data_dict.update(data)
            else:
                for k in self.fields:
                    if hasattr(data, k):
                        self.data_dict[k] = getattr(data, k)
                for k in ["title", "min_credits", "location_text", "contact_method"]:
                    if hasattr(data, k):
                        self.data_dict[k] = getattr(data, k)
        for k, v in kwargs.items():
            self.data_dict[k] = v

    def hidden_tag(self):
        token = session.get("csrf_token", "")
        return Markup(f'<input type="hidden" name="csrf_token" value="{escape(token)}">')

    def __getattr__(self, name: str):
        if name in self._fields_cache:
            return self._fields_cache[name]
        field_type = self.fields.get(name, "text")
        field = ShellField(name, field_type)
        if name in self.data_dict:
            field.data = self.data_dict[name]
        self._fields_cache[name] = field
        return field


class ShellField:
    def __init__(self, name: str, field_type: str = "text"):
        self.name = name
        self.field_type = field_type
        self.errors = []
        self.label = ShellLabel(name)
        self.choices = []
        self.data = None

    def __call__(self, *args, **kwargs):
        if self.data is not None and "value" not in kwargs and self.field_type not in ["select", "textarea", "submit"]:
            kwargs["value"] = self.data
        attrs = html_attrs(kwargs)
        if self.field_type == "textarea":
            val = escape(str(self.data)) if self.data is not None else ""
            return Markup(f'<textarea name="{self.name}" {attrs}>{val}</textarea>')
        if self.field_type == "select":
            options = []
            for val, lbl in self.choices:
                selected = ' selected' if self.data is not None and str(val) == str(self.data) else ''
                options.append(f'<option value="{escape(str(val))}"{selected}>{escape(str(lbl))}</option>')
            return Markup(f'<select name="{self.name}" {attrs}>{"".join(options)}</select>')
        if self.field_type == "submit":
            return Markup(f'<button type="submit" {attrs}>Save</button>')
        return Markup(f'<input type="{self.field_type}" name="{self.name}" {attrs}>')

    def __iter__(self):
        if self.name == "exchange_type":
            checked_credit = (self.data == "credit") or (self.data is None)
            checked_teach = (self.data == "teach")
            yield ShellRadioField(self.name, "credit", "Credit", checked=checked_credit)
            yield ShellRadioField(self.name, "teach", "Teach", checked=checked_teach)
        return


class ShellRadioField:
    def __init__(self, name: str, value: str, label: str, checked: bool = False):
        self.name = name
        self.value = value
        self.label = ShellTextLabel(label)
        self.checked = checked

    def __call__(self, *args, **kwargs):
        if self.checked:
            kwargs["checked"] = True
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
        "title": "text",
        "description": "textarea",
        "availability_labels": "textarea",
        "exchange_type": "select",
        "skill_id": "select",
        "category_id": "select",
        "min_credits": "text",
        "location_text": "text",
        "contact_method": "text",
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
