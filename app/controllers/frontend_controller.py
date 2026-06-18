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
from app.models.notification import Notification
from app.repositories import ExchangeRequestRepository, ExchangeRepository, ProfileReviewRepository, SkillRepository
from app.services import (
    MatchService,
    MessageService,
    NotificationService,
    ProfileService,
    SkillService,
    SkillSearchService,
)
from app.services.listing_catalog import (
    all_listings,
    categories,
    category_overview,
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
        message_service: MessageService,
        notification_service: NotificationService | None = None,
        match_service: MatchService | None = None,
    ):
        self._profile_service = profile_service
        self._skill_service = skill_service
        self._skill_search_service = skill_search_service
        self._message_service = message_service
        self._notification_service = notification_service or NotificationService()
        self._match_service = match_service

    def _get_filtered_listings(self):
        q = request.args.get("q", "").strip()
        listings = self._skill_service.search_listings(query=q if q else None, status="approved")
        for l in listings:
            l.distance = None
        
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

    def category_overview(self):
        return self.render(
            "listings/categories.html",
            category_overview=category_overview(),
            catalog_total=len(all_listings()),
        )

    @login_required
    def post_listing(self, listing_id: int | None = None):
        user = current_user
        categories_list = self._skill_service.get_all_categories()
        offered_skills = user.offered_skills

        listing = None
        if listing_id is not None:
            listing = self._skill_service.get_listing_by_id(listing_id)
            if not listing:
                abort(404)
            if listing.user_id != user.id:
                abort(403)

        errors: dict[str, str] = {}

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            exchange_type = request.form.get("exchange_type", "").strip()
            skill_id_raw = request.form.get("skill_id", "").strip()
            category_id_raw = request.form.get("category_id", "").strip()
            min_credits_raw = request.form.get("min_credits", "").strip()
            location_text = request.form.get("location_text", "").strip() or None
            contact_method = request.form.get("contact_method", "").strip() or None
            availability_labels = request.form.get("availability_labels", "").strip()

            if not title or len(title) < 5 or len(title) > 120:
                errors["title"] = "Title must be between 5 and 120 characters."

            if not description or len(description) < 10:
                errors["description"] = "Description must be at least 10 characters."

            skill_id = None
            if not skill_id_raw:
                errors["skill_id"] = "Please select a valid skill from your profile."
            else:
                try:
                    skill_id = int(skill_id_raw)
                    if not any(s.id == skill_id for s in offered_skills):
                        errors["skill_id"] = "Please select a valid skill from your profile."
                except ValueError:
                    errors["skill_id"] = "Please select a valid skill from your profile."

            category_id = None
            if not category_id_raw:
                errors["category_id"] = "Please select a valid category."
            else:
                try:
                    category_id = int(category_id_raw)
                    if not any(c.id == category_id for c in categories_list):
                        errors["category_id"] = "Please select a valid category."
                except ValueError:
                    errors["category_id"] = "Please select a valid category."

            if exchange_type not in {"credit", "teach"}:
                errors["exchange_type"] = "Please select a valid exchange type."

            credit_cost = 0
            if exchange_type == "credit":
                if not min_credits_raw:
                    errors["min_credits"] = "Please enter a valid number of credits."
                else:
                    try:
                        credit_cost = int(min_credits_raw)
                        if credit_cost < 0:
                            errors["min_credits"] = "Credits cannot be negative."
                    except ValueError:
                        errors["min_credits"] = "Please enter a valid number of credits."

            if not availability_labels:
                errors["availability_labels"] = "Please provide availability details."

            certificate_file = request.files.get("certificate")
            certificate_extension = None
            if certificate_file and certificate_file.filename:
                certificate_extension, cert_err = self._validate_certificate_upload(certificate_file)
                if cert_err:
                    errors["certificate"] = cert_err

            if not errors:
                certificate_path = None
                certificate_status = "none"

                from app.repositories import ProfileCertificateRepository
                cert_repo = ProfileCertificateRepository()

                if listing:
                    certificate_path = listing.certificate_path
                    certificate_status = listing.certificate_status

                    if request.form.get("remove_certificate") == "on":
                        certificate_path = None
                        certificate_status = "none"
                        cert_repo.delete_for_skill(user.id, listing.skill_id)

                if certificate_file and certificate_file.filename and certificate_extension:
                    certificate_path = self._save_certificate_upload(certificate_file, certificate_extension)
                    certificate_status = "pending"
                    selected_skill = next(s for s in offered_skills if s.id == skill_id)
                    cert_repo.upsert(
                        user_id=user.id,
                        skill_name=selected_skill.skill_name,
                        profile_skill_id=skill_id,
                        file_path=certificate_path,
                        status="pending"
                    )

                if listing:
                    self._skill_service.edit_listing(
                        listing_id=listing.id,
                        category_id=category_id,
                        skill_id=skill_id,
                        title=title,
                        description=description,
                        exchange_type=exchange_type,
                        credit_cost=credit_cost,
                        availability=availability_labels,
                        location_text=location_text,
                        contact_method=contact_method,
                        status="pending",
                    )
                    self._skill_service._skill_repository.update_certificate_info(
                        listing.id, certificate_path, certificate_status
                    )
                    flash("Listing updated successfully and is pending admin review.", "success")
                    return redirect(url_for("listings.mine"))
                else:
                    self._skill_service.create_listing(
                        user_id=user.id,
                        category_id=category_id,
                        skill_id=skill_id,
                        title=title,
                        description=description,
                        exchange_type=exchange_type,
                        credit_cost=credit_cost,
                        availability=availability_labels,
                        location_text=location_text,
                        contact_method=contact_method,
                        status="pending",
                        certificate_path=certificate_path,
                        certificate_status=certificate_status,
                    )
                    flash("Listing submitted successfully and is pending admin review.", "success")
                    return redirect(url_for("listings.mine"))

            form = ListingShellForm(data=request.form)
        else:
            if listing:
                form = ListingShellForm(data=listing, availability_labels=listing._availability_raw)
            else:
                form = ListingShellForm()

        form.skill_id.choices = [(s.id, s.skill_name) for s in offered_skills]
        form.category_id.choices = [(c.id, f"{c.icon} - {c.name}") for c in categories_list]

        return self.render(
            "listings/form.html",
            form=form,
            title="Edit listing" if listing else "Create listing",
            listing=listing,
            errors=errors,
        )

    @login_required
    def my_listings(self):
        listings = self._skill_service.get_listings_by_user(current_user.id)
        return self.render("listings/mine.html", listings=listings)

    def categories_overview(self):
        from app.repositories import CategoryRepository

        categories = CategoryRepository().all_with_counts()
        return self.render("listings/categories.html", categories=categories)

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
        form = RequestShellForm()
        if current_user.is_authenticated:
            form.offered_skill_id.choices = [
                (skill.id, skill.skill_name) for skill in current_user.offered_skills
            ]
        return self.render(
            "listings/detail.html",
            listing=listing,
            request_form=form,
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
        from app.repositories import (
            NotificationRepository,
            ProfileRepository,
            ProfileSkillRepository,
            RoleRepository,
            UserRepository,
        )

        if self._match_service is None:
            role_repo = RoleRepository()
            profile_repo = ProfileRepository()
            user_repo = UserRepository(role_repository=role_repo, profile_repository=profile_repo)
            self._match_service = MatchService(
                user_repository=user_repo,
                profile_skill_repository=ProfileSkillRepository(),
                notification_repository=NotificationRepository(),
            )

        try:
            matches = self._match_service.mutual_matches_for_user(current_user, notify=True)
        except Exception:
            matches = []
        return self.render(
            "matches/index.html",
            matches=matches,
            empty_state_reason=self._matches_empty_reason(current_user),
        )

    @staticmethod
    def _matches_empty_reason(user) -> str | None:
        if not user.offered_skills and not user.wanted_skills:
            return "Add offered and wanted skills to your profile to generate mutual matches."
        if not user.offered_skills:
            return "Add at least one offered skill so others can find you as a match."
        if not user.wanted_skills:
            return "Add at least one wanted skill to discover people who can help."
        return None

    @login_required
    def requests(self):
        pending = ExchangeRequestRepository().list_incoming_pending(current_user.id)
        history = ExchangeRequestRepository().list_incoming_history(current_user.id)
        return self.render(
            "requests/inbox.html",
            pending_requests=pending,
            history=history,
        )

    @login_required
    def sent_requests(self):
        sent = ExchangeRequestRepository().list_sent(current_user.id)
        return self.render("requests/sent.html", requests=sent)

    @login_required
    def exchanges(self):
        exchanges_list = ExchangeRepository().list_for_user(current_user.id)
        return self.render("exchanges/index.html", exchanges=exchanges_list)

    @login_required
    def exchange_detail(self, exchange_id: int):
        exchange_repo = ExchangeRepository()
        review_repo = ProfileReviewRepository()
        exchange = exchange_repo.find_by_id(exchange_id)
        if not exchange:
            abort(404)
        request_obj = exchange.request
        if not request_obj:
            abort(404)
        listing = request_obj.listing
        if not listing:
            abort(404)
        if current_user.id not in [request_obj.learner_id, listing.user_id]:
            abort(403)
        completion_marks = exchange_repo.completion_marks(exchange.id)
        existing_review = review_repo.find_for_exchange_by_reviewer(exchange.id, current_user.id)
        return self.render(
            "exchanges/detail.html",
            exchange=exchange,
            can_mark_complete=current_user.id not in {mark.user_id for mark in completion_marks},
            can_review=exchange_repo.is_fully_completed(exchange.id) and existing_review is None,
            reviews=review_repo.for_exchange(exchange.id),
        )

    @login_required
    def mark_exchange_complete(self, exchange_id: int):
        exchange_repo = ExchangeRepository()
        exchange = exchange_repo.find_by_id(exchange_id)
        if not exchange:
            abort(404)
        if not exchange_repo.is_participant(exchange_id, current_user.id):
            abort(403)

        exchange = exchange_repo.mark_complete(exchange_id=exchange_id, user_id=current_user.id)
        if exchange.status == "completed":
            flash("Both parties have marked this exchange complete. Reviews are now open.", "success")
        else:
            flash("Your completion mark has been recorded.", "success")
        return redirect(url_for("exchanges.detail", exchange_id=exchange_id))

    @login_required
    def create_request(self, listing_id: int):
        listing = SkillRepository().find_by_id(listing_id)
        if not listing:
            abort(404)
        if current_user.id == listing.user_id:
            flash("You cannot request your own listing.", "danger")
            return redirect(url_for("listings.detail", listing_id=listing_id))
        
        if listing.exchange_type == "credit":
            if current_user.available_credit_balance < listing.credit_cost:
                flash("Your available credit balance is insufficient to request this skill.", "danger")
                return redirect(url_for("listings.detail", listing_id=listing_id))
        
        offered_skill_id = request.form.get("offered_skill_id")
        if offered_skill_id:
            offered_skill_id = int(offered_skill_id)
        else:
            offered_skill_id = None
            
        requested_message = request.form.get("requested_message", "").strip() or None
        
        ExchangeRequestRepository().create(
            listing_id=listing_id,
            learner_id=current_user.id,
            offered_skill_id=offered_skill_id,
            requested_message=requested_message,
        )
        self._notification_service.notify_exchange_request(
            user_id=listing.user_id,
            requester_name=current_user.full_name,
            skill_title=listing.title,
            target_url="/requests/inbox",
        )
        flash("Your request has been submitted.", "success")
        return redirect(url_for("requests_bp.sent"))

    @login_required
    def accept_request(self, request_id: int):
        request_obj = ExchangeRequestRepository().find_by_id(request_id)
        if not request_obj:
            abort(404)
        listing = request_obj.listing
        if not listing:
            abort(404)
        if current_user.id != listing.user_id:
            abort(403)
        if request_obj.status != "pending":
            return redirect(url_for("requests_bp.inbox"))
            
        ExchangeRequestRepository().update_status(request_id, "accepted")
        ExchangeRepository().create(request_id=request_id)
        
        self._message_service.create_conversation(
            subject=f"Exchange: {listing.title}",
            permission_source="accepted_exchange",
            participant_ids=[listing.user_id, request_obj.learner_id],
        )

        self._notification_service.notify_request_accepted(
            user_id=request_obj.learner_id,
            skill_title=listing.title,
            target_url="/requests/inbox",
        )

        flash("Request accepted and exchange created.", "success")
        return redirect(url_for("requests_bp.inbox"))

    @login_required
    def decline_request(self, request_id: int):
        request_obj = ExchangeRequestRepository().find_by_id(request_id)
        if not request_obj:
            abort(404)
        listing = request_obj.listing
        if not listing:
            abort(404)
        if current_user.id != listing.user_id:
            abort(403)
        if request_obj.status != "pending":
            return redirect(url_for("requests_bp.inbox"))
            
        decline_reason = request.form.get("decline_reason", "").strip() or None
        ExchangeRequestRepository().update_status(request_id, "declined", decline_reason=decline_reason)

        self._notification_service.notify_request_declined(
            user_id=request_obj.learner_id,
            skill_title=listing.title,
            reason=decline_reason,
            target_url="/requests/inbox",
        )

        flash("Request declined.", "warning")
        return redirect(url_for("requests_bp.inbox"))

    @login_required
    def cancel_request(self, request_id: int):
        request_obj = ExchangeRequestRepository().find_by_id(request_id)
        if not request_obj:
            abort(404)
        if current_user.id != request_obj.learner_id:
            abort(403)
        if request_obj.status != "pending":
            return redirect(url_for("requests_bp.sent"))
            
        ExchangeRequestRepository().update_status(request_id, "cancelled")
        
        flash("Request cancelled.", "info")
        return redirect(url_for("requests_bp.sent"))

    @login_required
    def messages(self):
        conversations = self._message_service.list_conversations(current_user.id)
        active_conversation = conversations[0] if conversations else None
        ordered_messages = []
        if active_conversation:
            active_conversation = self._message_service.get_conversation(active_conversation.id, current_user.id)
            if active_conversation:
                self._message_service.mark_read(
                    conversation_id=active_conversation.id,
                    user_id=current_user.id,
                )
                conversations = self._message_service.list_conversations(current_user.id)
                ordered_messages = active_conversation.messages
        return self.render(
            "messages/index.html",
            conversations=conversations,
            conversation=active_conversation,
            ordered_messages=ordered_messages,
            form=MessageShellForm(),
        )

    @login_required
    def conversation(self, conversation_id: int):
        conversation = self._message_service.get_conversation(conversation_id, current_user.id)
        if not conversation:
            abort(404)
        if request.method == "POST":
            body = request.form.get("body", "")
            try:
                self._message_service.send_message(
                    conversation_id=conversation_id,
                    sender_id=current_user.id,
                    body=body,
                )
            except ValueError as exc:
                flash(str(exc), "danger")
            except PermissionError:
                abort(403)
            else:
                flash("Message sent.", "success")
                return redirect(url_for("messages.detail", conversation_id=conversation_id))

        self._message_service.mark_read(conversation_id=conversation_id, user_id=current_user.id)
        conversation = self._message_service.get_conversation(conversation_id, current_user.id)
        conversations = self._message_service.list_conversations(current_user.id)
        return self.render(
            "messages/detail.html",
            conversation=conversation,
            conversations=conversations,
            ordered_messages=conversation.messages,
            form=MessageShellForm(),
        )

    @login_required
    def notifications(self):
        return self.render("notifications/index.html", notifications=[])

    @login_required
    def notification_counts(self):
        return jsonify(
            {
                "messages": 0,
                "notifications": self._notification_service.unread_count(current_user.id),
            }
        )

    @login_required
    def mark_all_notifications_read(self):
        updated = self._notification_service.mark_all_read(current_user.id)
        if updated:
            flash(f"{updated} notification{'s' if updated != 1 else ''} marked as read.", "success")
        else:
            flash("No unread notifications to mark.", "info")
        return redirect(url_for("notifications.index"))

    @login_required
    def open_notification(self, notification_id: int):
        notification = self._notification_service.mark_read(current_user.id, notification_id)
        if not notification:
            flash("Notification not found.", "warning")
            return redirect(url_for("notifications.index"))
        target_url = notification.target_url or url_for("notifications.index")
        if not target_url.startswith("/") or target_url.startswith("//"):
            target_url = url_for("notifications.index")
        return redirect(target_url)

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

        return self.render(
            "profile/edit.html",
            form=ProfileShellForm(),
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

    def _validate_certificate_upload(self, certificate) -> tuple[str | None, str | None]:
        filename = secure_filename(certificate.filename or "")
        extension = Path(filename).suffix.lower()
        allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg"}
        allowed_mimetypes = {"application/pdf", "image/png", "image/jpeg"}
        if extension not in allowed_extensions:
            return None, "Certificate must be a PDF, JPG, or PNG file."
        if certificate.mimetype not in allowed_mimetypes:
            return None, "Certificate file type is not supported."

        try:
            certificate.stream.seek(0, os.SEEK_END)
            size = certificate.stream.tell()
            certificate.stream.seek(0)
            header = certificate.stream.read(16)
            certificate.stream.seek(0)
        except OSError:
            return None, "Certificate could not be read. Please choose another file."

        if size <= 0:
            return None, "Certificate file is empty."
        if size > 10 * 1024 * 1024:
            return None, "Certificate must be under 10MB."

        if extension == ".pdf" and not header.startswith(b"%PDF"):
            return None, "Certificate file content must match the PDF format."
        if extension == ".png" and not header.startswith(b"\x89PNG\r\n\x1a\n"):
            return None, "Certificate file content must match the PNG format."
        if extension in {".jpg", ".jpeg"} and not header.startswith(b"\xff\xd8\xff"):
            return None, "Certificate file content must match the JPG format."

        return extension, None

    def _save_certificate_upload(self, certificate, extension: str) -> str:
        cert_dir = Path(current_app.config["UPLOAD_FOLDER"]) / "certificates"
        cert_dir.mkdir(parents=True, exist_ok=True)
        filename = f"user-{current_user.id}-cert-{uuid4().hex}{extension}"
        certificate.stream.seek(0)
        certificate.save(cert_dir / filename)
        return f"certificates/{filename}"

    @login_required
    def certificates(self):
        user = current_user
        from app.repositories import ProfileCertificateRepository
        cert_repo = ProfileCertificateRepository()

        if request.method == "POST":
            skill_id_raw = request.form.get("skill_id", "").strip()
            certificate_file = request.files.get("certificate")

            skill_id = None
            selected_skill = None
            if not skill_id_raw:
                flash("Please select a valid skill.", "danger")
            else:
                try:
                    skill_id = int(skill_id_raw)
                    selected_skill = next((s for s in user.offered_skills if s.id == skill_id), None)
                    if not selected_skill:
                        flash("Please select a valid skill from your profile.", "danger")
                except ValueError:
                    flash("Please select a valid skill.", "danger")

            if selected_skill and certificate_file and certificate_file.filename:
                extension, err = self._validate_certificate_upload(certificate_file)
                if err:
                    flash(err, "danger")
                else:
                    certificate_path = self._save_certificate_upload(certificate_file, extension)

                    cert_repo.upsert(
                        user_id=user.id,
                        skill_name=selected_skill.skill_name,
                        profile_skill_id=skill_id,
                        file_path=certificate_path,
                        status="pending",
                    )

                    self._skill_service._skill_repository.update_certificate_info_by_skill_id(
                        user.id, skill_id, certificate_path, "pending"
                    )

                    flash("Certificate uploaded successfully and is pending admin review.", "success")
                    return redirect(url_for("profile.certificates"))
            elif not certificate_file or not certificate_file.filename:
                flash("Please choose a certificate file to upload.", "danger")

        certificates = cert_repo.find_by_user_id(user.id)
        form = CertificateShellForm()
        form.skill_id.choices = [(s.id, s.skill_name) for s in user.offered_skills]
        return self.render("profile/certificates.html", form=form, certificates=certificates)

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

    @login_required
    def report_user(self, user_id: int):
        target_user = User.find_by_id(user_id)
        if not target_user:
            abort(404)
        if target_user.id == current_user.id:
            flash("You cannot report yourself.", "danger")
            return redirect(url_for("profile.view", user_id=user_id))

        if request.method == "POST":
            from app.repositories import ReportRepository
            report_repo = ReportRepository()
            if report_repo.has_recent_report(current_user.id, target_user.id, within_days=7):
                flash("You cannot submit duplicate reports against the same user within a 7-day window.", "danger")
                return redirect(url_for("profile.view", user_id=user_id))

            reason = request.form.get("reason", "").strip()
            description = request.form.get("description", "").strip() or None

            valid_reasons = {"spam", "harassment", "fake_profile", "fraud", "other"}
            if not reason or reason not in valid_reasons:
                flash("Invalid report reason selected.", "danger")
                return redirect(url_for("profile.view", user_id=user_id))

            report_repo.create(
                reporter_id=current_user.id,
                reported_user_id=target_user.id,
                reason=reason,
                description=description,
            )

            self._notification_service.notify_report_received(
                user_id=current_user.id,
                reported_name=target_user.full_name,
                target_url=url_for("profile.view", user_id=user_id),
            )

            flash("Your report has been submitted to the admin review team.", "success")
            return redirect(url_for("profile.view", user_id=user_id))

        return redirect(url_for("profile.view", user_id=user_id))

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
        exchange_repo = ExchangeRepository()
        review_repo = ProfileReviewRepository()
        exchange = exchange_repo.find_by_id(exchange_id)
        if not exchange:
            abort(404)
        request_obj = exchange.request
        listing = request_obj.listing if request_obj else None
        if not request_obj or not listing:
            abort(404)
        if current_user.id not in [request_obj.learner_id, listing.user_id]:
            abort(403)
        if not exchange_repo.is_fully_completed(exchange.id):
            flash("Reviews unlock after both parties mark the exchange complete.", "warning")
            return redirect(url_for("exchanges.detail", exchange_id=exchange.id))
        if review_repo.find_for_exchange_by_reviewer(exchange.id, current_user.id):
            flash("You have already reviewed this completed exchange.", "info")
            return redirect(url_for("exchanges.detail", exchange_id=exchange.id))

        reviewee = exchange.teacher if current_user.id == request_obj.learner_id else exchange.learner
        if not reviewee:
            abort(404)

        form = ReviewShellForm(data={"rating": request.form.get("rating", ""), "comment": request.form.get("comment", "")})
        if request.method == "POST":
            rating_raw = request.form.get("rating", "").strip()
            comment = request.form.get("comment", "").strip()
            rating = None
            try:
                rating = int(rating_raw)
            except ValueError:
                form.rating.errors.append("Choose a star rating from 1 to 5.")
            else:
                if rating < 1 or rating > 5:
                    form.rating.errors.append("Choose a star rating from 1 to 5.")
            if len(comment) > 500:
                form.comment.errors.append("Comment must be 500 characters or fewer.")

            if not form.rating.errors and not form.comment.errors:
                review_repo.create(
                    exchange_id=exchange.id,
                    reviewee_user_id=reviewee.id,
                    reviewer_id=current_user.id,
                    reviewer_name=current_user.full_name,
                    rating=rating,
                    comment=comment or None,
                )
                self._notification_service.notify_new_review(
                    user_id=reviewee.id,
                    reviewer_name=current_user.full_name,
                    target_url=url_for("profile.view", user_id=reviewee.id),
                )
                flash("Your review has been published.", "success")
                return redirect(url_for("profile.view", user_id=reviewee.id))

        return self.render("reviews/form.html", form=form, exchange=exchange, reviewee=reviewee)

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
                for key in self.fields:
                    if hasattr(data, key):
                        self.data_dict[key] = getattr(data, key)
                for key in ["title", "min_credits", "location_text", "contact_method"]:
                    if hasattr(data, key):
                        self.data_dict[key] = getattr(data, key)
        for key, value in kwargs.items():
            self.data_dict[key] = value

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
            for value, label in self.choices:
                selected = ' selected' if self.data is not None and str(value) == str(self.data) else ""
                options.append(f'<option value="{escape(str(value))}"{selected}>{escape(str(label))}</option>')
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reason.choices = [
            ("spam", "Spam"),
            ("harassment", "Harassment"),
            ("fake_profile", "Fake Profile"),
            ("fraud", "Fraud"),
            ("other", "Other"),
        ]


class ReviewShellForm(ShellForm):
    fields = {"rating": "select", "comment": "textarea", "submit": "submit"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rating.choices = [
            ("", "Choose a rating"),
            ("5", "5 stars"),
            ("4", "4 stars"),
            ("3", "3 stars"),
            ("2", "2 stars"),
            ("1", "1 star"),
        ]


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
