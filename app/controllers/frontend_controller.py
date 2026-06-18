from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from flask import abort, current_app, flash, jsonify, redirect, request, session, url_for
from flask_login import current_user, login_required
from markupsafe import Markup, escape
from werkzeug.utils import secure_filename

from app.exceptions import ProfileNotFoundError
from app.models import Profile, ProfileCertificate, ProfileReview, ProfileSkill, User
from app.services import ProfileService, SkillService, SkillSearchService
from app.services.listing_catalog import (
    all_listings,
    categories,
    filter_listings,
    find_listing,
    paginate_listings,
)

from .base_controller import BaseController

MAX_AVATAR_BYTES = 5 * 1024 * 1024
ALLOWED_AVATAR_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_AVATAR_MIMETYPES = {"image/jpeg", "image/png"}


class FrontendController(BaseController):
    def __init__(
        self,
        profile_service: ProfileService,
        skill_service: SkillService,
        skill_search_service: SkillSearchService,
    ):
        self._profile_service = profile_service
        self._skill_service = skill_service
        self._skill_search_service = skill_search_service

    def _get_filtered_listings(self):
        q = request.args.get("q", "").strip()
        
        category_ids = []
        raw_cats = request.args.getlist("category") + request.args.getlist("category[]")
        for cid in raw_cats:
            if "," in cid:
                for part in cid.split(","):
                    part = part.strip()
                    if part.isdigit():
                        category_ids.append(int(part))
            else:
                cid = cid.strip()
                if cid.isdigit():
                    category_ids.append(int(cid))
                    
        try:
            user_lat = float(request.args.get("lat", ""))
            user_lng = float(request.args.get("lng", ""))
            radius_km = min(int(request.args.get("radius", 10)), 100)
            
            listings = self._skill_service.search_listings_by_location(
                user_lat=user_lat,
                user_lng=user_lng,
                radius_km=radius_km,
                query=q if q else None,
                category_ids=category_ids if category_ids else None,
                status="approved"
            )
            
            session["last_lat"] = user_lat
            session["last_lng"] = user_lng
            session["last_loc_label"] = request.args.get("label", "")
            return listings
        except (ValueError, TypeError):
            pass

        listings = self._skill_service.search_listings(query=q if q else None, status="approved")
        for l in listings:
            l.distance = None
            
        if category_ids:
            listings = [l for l in listings if l.category_id in category_ids]
            
        location_query = request.args.get("location", "").strip()
        radius_query = request.args.get("radius", "").strip()
        if location_query:
            from app.utils.distance import parse_coordinates, haversine_distance
            search_coords = parse_coordinates(location_query)
            radius_km = None
            if radius_query:
                try:
                    radius_km = float(radius_query)
                except ValueError:
                    pass
            filtered_listings = []
            for l in listings:
                l_loc_str = l.location_text.strip() if l.location_text else None
                if not l_loc_str and l.user and l.user.profile and l.user.profile.location:
                    l_loc_str = l.user.profile.location.strip()
                l_coords = parse_coordinates(l_loc_str) if l_loc_str else None
                if search_coords and l_coords:
                    dist = haversine_distance(search_coords, l_coords)
                    l.distance = dist
                    if radius_km is None or dist <= radius_km:
                        filtered_listings.append(l)
                elif not search_coords and l_loc_str and location_query.lower() in l_loc_str.lower():
                    l.distance = None
                    filtered_listings.append(l)
            listings = filtered_listings
        return listings

    @login_required
    def update_location_coords(self):
        data = request.get_json(silent=True) or {}
        try:
            lat = float(data.get("lat"))
            lng = float(data.get("lng"))
            label = str(data.get("label", ""))[:255]
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Invalid coordinates"}), 400

        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            return jsonify({"ok": False, "error": "Coordinates out of range"}), 400

        self._profile_service.save_location_coords(current_user.id, lat, lng, label)
        return jsonify({"ok": True, "label": label})


    def _categories(self):
        return self._skill_service.get_all_categories()

    def marketplace(self):
        listings = self._get_filtered_listings()
        categories = self._categories()
        
        page = request.args.get("page", 1, type=int)
        per_page = 6
        total_results = len(listings)
        total_pages = max(1, (total_results + per_page - 1) // per_page)
        
        start = (page - 1) * per_page
        end = start + per_page
        paginated_listings = listings[start:end]
        
        catalog_total = len(self._skill_service.search_listings(status="approved"))
        
        return self.render(
            "listings/index.html",
            listings=paginated_listings,
            categories=categories,
            page=page,
            total_pages=total_pages,
            total_results=total_results,
            saved_listing_ids=self._saved_listing_ids(),
            active_filters=self._active_filters(),
            catalog_total=catalog_total,
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

    def saved_listings(self):
        saved_ids = self._saved_listing_ids()
        listings = []
        for lid in saved_ids:
            l = self._skill_service.get_listing_by_id(lid)
            if l:
                listings.append(l)
        return self.render(
            "listings/saved.html",
            listings=listings,
            saved_listing_ids=saved_ids,
            total_results=len(listings),
        )

    def listing_detail(self, listing_id: int):
        listing = self._skill_service.get_listing_by_id(listing_id)
        if not listing:
            abort(404)
        return self.render(
            "listings/detail.html",
            listing=listing,
            request_form=RequestShellForm(),
            saved_listing_ids=self._saved_listing_ids(),
        )

    def api_search(self):
        listings = self._get_filtered_listings()
        page = request.args.get("page", 1, type=int)
        per_page = 6
        total_results = len(listings)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_listings = listings[start:end]
        
        html = self.render(
            "partials/listing_cards.html",
            listings=paginated_listings,
            saved_listing_ids=self._saved_listing_ids(),
        )
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

    def save_listing(self, listing_id: int):
        if self._skill_service.get_listing_by_id(listing_id) is None:
            abort(404)
        saved_ids = self._saved_listing_ids()
        saved_ids.add(listing_id)
        self._store_saved_listing_ids(saved_ids)
        flash("Listing saved to your browse list.", "success")
        return redirect(request.referrer or url_for("listings.saved"))

    def unsave_listing(self, listing_id: int):
        saved_ids = self._saved_listing_ids()
        saved_ids.discard(listing_id)
        self._store_saved_listing_ids(saved_ids)
        flash("Listing removed from your saved list.", "info")
        return redirect(request.referrer or url_for("listings.saved"))

    @login_required
    def wallet(self):
        return self.render("credits/ledger.html", entries=[], holds=[])

    @login_required
    def matches(self):
        from app.models.user import Profile
        matches = Profile.get_mutual_matches(current_user.id)
        return self.render("matches/index.html", matches=matches)

    def _notify_new_matches(self, user_id: int):
        from app.models.user import User, Profile
        from app.models.notification import Notification

        current_matches = Profile.get_mutual_matches(user_id)
        existing_notified = Notification.get_notified_match_ids(user_id)

        my_profile = User.find_by_id(user_id)

        for match in current_matches:
            mid = match["matched_user_id"]
            if mid not in existing_notified:
                Notification.create_new_match_notification(user_id, match["name"], mid)
                if my_profile:
                    Notification.create_new_match_notification(mid, my_profile.full_name, user_id)

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
        from app.models.notification import Notification
        unread = Notification.get_unread_count(current_user.id)
        return jsonify({"messages": 0, "notifications": unread})

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
                self._notify_new_matches(user.id)
                flash("Profile updated successfully.", "success")
                return redirect(url_for("profile.edit"))

        return self.render(
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
        return self.render("profile/certificates.html", form=CertificateShellForm(), certificates=[])

    def profile_view(self, user_id: int):
        try:
            page_data = self._profile_service.get_profile_page_data(user_id)
        except ProfileNotFoundError:
            abort(404)
            
        score_data = ProfileReview.get_reputation_score(user_id)
        from app.models.profile import get_score_tier
        tier = get_score_tier(score_data['score'], score_data['count'])
            
        return self.render(
            "profile/view.html",
            user=page_data.user,
            approved_listings=page_data.approved_listings,
            approved_certificates=page_data.approved_certificates,
            recent_reviews=page_data.recent_reviews,
            report_form=ReportShellForm(),
            score=score_data['score'],
            count=score_data['count'],
            tier=tier,
        )

    @login_required
    def get_reputation_json(self, user_id: int):
        score_data = ProfileReview.get_reputation_score(user_id)
        from app.models.profile import get_score_tier
        tier = get_score_tier(score_data["score"], score_data["count"])
        return jsonify({
            "score": score_data["score"],
            "count": score_data["count"],
            "tier": tier,
        })

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

    def _browse_page(self, page: int | None = None):
        selected_categories = self._selected_category_ids()
        listings = filter_listings(
            query=request.args.get("q", ""),
            category_ids=selected_categories,
            radius=request.args.get("radius", ""),
        )
        current_page = page if page is not None else request.args.get("page", 1, type=int) or 1
        return paginate_listings(listings, current_page)

    @staticmethod
    def _selected_category_ids() -> set[int]:
        selected_ids = set()
        for raw_category_id in request.args.getlist("category"):
            try:
                selected_ids.add(int(raw_category_id))
            except ValueError:
                continue
        return selected_ids

    @staticmethod
    def _saved_listing_ids() -> set[int]:
        saved_ids = set()
        for listing_id in session.get("saved_listing_ids", []):
            try:
                saved_ids.add(int(listing_id))
            except (TypeError, ValueError):
                continue
        return saved_ids

    @staticmethod
    def _store_saved_listing_ids(saved_ids: set[int]) -> None:
        session["saved_listing_ids"] = sorted(saved_ids)
        session.modified = True

    def _active_filters(self) -> list[dict[str, str]]:
        filters = []
        query = request.args.get("q", "").strip()
        if query:
            filters.append({"label": f"Keyword: {query}", "remove_url": self._filter_remove_url("q")})
        category_lookup = {category.id: category.name for category in self._categories()}
        for category_id in self._selected_category_ids():
            if category_id in category_lookup:
                filters.append(
                    {
                        "label": f"Category: {category_lookup[category_id]}",
                        "remove_url": self._filter_remove_url("category", str(category_id)),
                    }
                )
        radius = request.args.get("radius", "").strip()
        if radius:
            filters.append({"label": f"Radius: {radius} km", "remove_url": self._filter_remove_url("radius")})
        return filters

    @staticmethod
    def _filter_remove_url(key: str, value: str | None = None) -> str:
        params = request.args.to_dict(flat=False)
        params.pop("page", None)
        if value is None:
            params.pop(key, None)
        else:
            remaining = [item for item in params.get(key, []) if item != value]
            if remaining:
                params[key] = remaining
            else:
                params.pop(key, None)
        return url_for("listings.index", **params)


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
