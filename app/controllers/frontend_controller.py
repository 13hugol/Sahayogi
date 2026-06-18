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
from app.repositories import ExchangeRequestRepository, ExchangeRepository, SkillRepository
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
        db_listings = self._skill_service.search_listings(query=q if q else None, status="approved")
        for l in db_listings:
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
            db_listings = [l for l in db_listings if l.category_id in category_ids]
            
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
            for l in db_listings:
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
            db_listings = filtered_listings

        try:
            has_db_listings = len(self._skill_service.search_listings(status="approved")) > 0
            if has_db_listings:
                return db_listings

            from app.services.listing_catalog import filter_listings as catalog_filter_listings
            mock_listings = catalog_filter_listings(
                query=q,
                category_ids=set(category_ids),
                radius=radius_query,
            )
            for m in mock_listings:
                if location_query:
                    m.distance = None
            return db_listings + mock_listings
        except Exception:
            return db_listings

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
        try:
            from app.services.listing_catalog import all_listings
            catalog_total += len([l for l in all_listings() if l.status == "approved"])
        except Exception:
            pass
        
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
        if not skill_choices:
            skill_choices = [("", "Please add offered skills to your profile first")]
        categories = self._skill_service.get_all_categories()
        category_choices = [("", "Choose one category")] + [(c.id, f"{c.icon} - {c.name}") for c in categories]
        
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
        from app.repositories.credit_repository import CreditRepository
        credit_repo = CreditRepository()
        entries = credit_repo.get_history_for_user(current_user.id)
        holds = credit_repo.get_active_holds_for_user(current_user.id)
        return self.render("credits/ledger.html", entries=entries, holds=holds)

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
        selected_status = request.args.get("status", "").strip()
        date_from = self._parse_filter_date(request.args.get("date_from", ""))
        date_to = self._parse_filter_date(request.args.get("date_to", ""))
        exchanges_list = ExchangeRepository().list_for_user(
            current_user.id,
            status=selected_status or None,
            date_from=date_from,
            date_to=date_to,
        )
        from app.repositories import ProfileReviewRepository
        reviewed_exchange_ids = ProfileReviewRepository().reviewed_exchange_ids(current_user.id)
        return self.render(
            "exchanges/index.html",
            exchanges=exchanges_list,
            selected_status=selected_status,
            date_from=date_from or "",
            date_to=date_to or "",
            reviewed_exchange_ids=reviewed_exchange_ids,
        )

    @staticmethod
    def _parse_filter_date(raw: str) -> str | None:
        from datetime import datetime

        raw = (raw or "").strip()
        if not raw:
            return None
        try:
            datetime.strptime(raw, "%Y-%m-%d")
        except ValueError:
            return None
        return raw

    @login_required
    def exchange_detail(self, exchange_id: int):
        exchange = ExchangeRepository().find_by_id(exchange_id)
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
        from app.repositories import ProfileReviewRepository
        review_repo = ProfileReviewRepository()
        can_mark_complete = (
            exchange.status == "active"
            and not exchange.completed_by(current_user.id)
        )
        already_reviewed = review_repo.find_by_exchange_and_reviewer(exchange.id, current_user.id) is not None
        can_review = exchange.status == "completed" and not already_reviewed
        return self.render(
            "exchanges/detail.html",
            exchange=exchange,
            can_mark_complete=can_mark_complete,
            can_review=can_review,
            reviews=review_repo.for_exchange(exchange.id),
        )

    @login_required
    def mark_complete(self, exchange_id: int):
        exchange = ExchangeRepository().find_by_id(exchange_id)
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
        if exchange.status != "active":
            flash("This exchange is not active.", "warning")
            return redirect(url_for("exchanges.detail", exchange_id=exchange_id))

        is_learner = current_user.id == request_obj.learner_id
        if exchange.completed_by(current_user.id):
            flash("You have already confirmed completion. Waiting for the other participant.", "info")
            return redirect(url_for("exchanges.detail", exchange_id=exchange_id))

        from datetime import datetime
        completed_at = datetime.utcnow()
        from app.database import Database

        mark_column = "learner_completed_at" if is_learner else "teacher_completed_at"
        other_already_marked = (
            exchange.teacher_completed_at if is_learner else exchange.learner_completed_at
        ) is not None

        db = Database()
        try:
            with db.transaction():
                db.execute(
                    f"UPDATE exchanges SET {mark_column} = %s WHERE id = %s",
                    (completed_at, exchange_id),
                )
                if other_already_marked:
                    db.execute(
                        "UPDATE exchanges SET status = 'completed', completed_at = %s WHERE id = %s",
                        (completed_at, exchange_id),
                    )
                    if listing.exchange_type == "credit":
                        db.execute(
                            "UPDATE credit_holds SET status = 'cleared' WHERE request_id = %s AND status = 'active'",
                            (request_obj.id,),
                        )
                        # Deduct from learner
                        db.execute(
                            """
                            INSERT INTO credit_transactions (user_id, amount_delta, entry_type, description, skill_id, exchange_id)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (request_obj.learner_id, -listing.credit_cost, "deduction", f"Spent on learning '{listing.title}'", listing.id, exchange.id),
                        )
                        db.execute(
                            "UPDATE users SET credit_balance = credit_balance - %s WHERE id = %s",
                            (listing.credit_cost, request_obj.learner_id),
                        )
                        # Credit to teacher
                        db.execute(
                            """
                            INSERT INTO credit_transactions (user_id, amount_delta, entry_type, description, skill_id, exchange_id)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (listing.user_id, listing.credit_cost, "earning", f"Earned from teaching '{listing.title}'", listing.id, exchange.id),
                        )
                        db.execute(
                            "UPDATE users SET credit_balance = credit_balance + %s WHERE id = %s",
                            (listing.credit_cost, listing.user_id),
                        )
                    db.execute(
                        "UPDATE profiles SET completed_exchange_count = completed_exchange_count + 1 WHERE user_id IN (%s, %s)",
                        (request_obj.learner_id, listing.user_id),
                    )
        finally:
            db.close()

        other_user_id = listing.user_id if is_learner else request_obj.learner_id
        if other_already_marked:
            self._notification_service.create_notification(
                user_id=other_user_id,
                title="Exchange Completed",
                body=f"Your exchange for '{listing.title}' has been marked completed.",
                target_url=f"/exchanges/{exchange.id}",
            )
            flash("Exchange marked completed successfully.", "success")
        else:
            self._notification_service.create_notification(
                user_id=other_user_id,
                title="Completion confirmation needed",
                body=f"{current_user.full_name} marked '{listing.title}' as complete. Confirm to finish the exchange.",
                target_url=f"/exchanges/{exchange.id}",
            )
            flash("Completion recorded. Waiting for the other participant to confirm.", "success")
        return redirect(url_for("exchanges.detail", exchange_id=exchange_id))

    @login_required
    def video_call_room(self, exchange_id: int):
        from app.repositories import ExchangeRepository
        exchange = ExchangeRepository().find_by_id(exchange_id)
        if not exchange:
            abort(404)
        if exchange.status != "active":
            flash("This exchange is not active.", "warning")
            return redirect(url_for("exchanges.detail", exchange_id=exchange_id))
        
        request_obj = exchange.request
        listing = exchange.listing
        if not request_obj or not listing:
            abort(404)
        if current_user.id not in [request_obj.learner_id, listing.user_id]:
            abort(403)
            
        return self.render("exchanges/video.html", exchange=exchange)

    @login_required
    def start_video_call(self, exchange_id: int):
        from app.repositories import ExchangeRepository
        from app.models.user import User
        
        exchange = ExchangeRepository().find_by_id(exchange_id)
        if not exchange:
            abort(404)
        if exchange.status != "active":
            flash("This exchange is not active.", "warning")
            return redirect(url_for("exchanges.detail", exchange_id=exchange_id))
            
        request_obj = exchange.request
        listing = exchange.listing
        if not request_obj or not listing:
            abort(404)
        if current_user.id not in [request_obj.learner_id, listing.user_id]:
            abort(403)
            
        # Check if both are online
        learner = User.find_by_id(request_obj.learner_id)
        teacher = User.find_by_id(listing.user_id)
        
        if not learner or not teacher or not learner.is_online or not teacher.is_online:
            flash("Both participants must be online to start a video call.", "danger")
            return redirect(url_for("messages.detail", conversation_id=exchange.conversation.id))
            
        ExchangeRepository().start_video_call(exchange_id)
        
        # Post system message to the chat
        conversation = exchange.conversation
        if conversation:
            from app.repositories import MessageRepository
            msg_body = "Video call started. Join from this conversation while the exchange is active."
            MessageRepository().create_message(
                conversation_id=conversation.id,
                sender_id=current_user.id,
                body=msg_body
            )
            
        return redirect(url_for("exchanges.video_call_room", exchange_id=exchange_id))

    @login_required
    def end_video_call(self, exchange_id: int):
        from app.repositories import ExchangeRepository
        from datetime import datetime
        
        exchange = ExchangeRepository().find_by_id(exchange_id)
        if not exchange:
            abort(404)
            
        request_obj = exchange.request
        listing = exchange.listing
        if not request_obj or not listing:
            abort(404)
        if current_user.id not in [request_obj.learner_id, listing.user_id]:
            abort(403)
            
        if not exchange.video_call_active:
            flash("No active video call was found for this exchange.", "warning")
            return redirect(url_for("exchanges.detail", exchange_id=exchange_id))
            
        # Compute duration
        started_at = exchange.video_call_started_at
        if started_at:
            if started_at.tzinfo is not None:
                started_at = started_at.replace(tzinfo=None)
            duration_sec = int((datetime.utcnow() - started_at).total_seconds())
            mins = duration_sec // 60
            secs = duration_sec % 60
            duration_str = f"{mins}m {secs}s"
        else:
            duration_str = "unknown duration"
            
        summary = f"Video call ended. Duration: {duration_str}. Participants: {exchange.learner.full_name} and {exchange.teacher.full_name}."
        ExchangeRepository().end_video_call(exchange_id, summary)
        
        # Post system message to the chat
        conversation = exchange.conversation
        if conversation:
            from app.repositories import MessageRepository
            msg_body = f"Video call ended. Duration: {duration_str}."
            MessageRepository().create_message(
                conversation_id=conversation.id,
                sender_id=current_user.id,
                body=msg_body
            )
            
        flash(f"Video call ended. {summary}", "success")
        return redirect(url_for("exchanges.detail", exchange_id=exchange_id))

    @login_required
    def video_call_heartbeat(self, exchange_id: int):
        from app.repositories import ExchangeRepository
        from app.models.user import User
        from datetime import datetime
        
        exchange = ExchangeRepository().find_by_id(exchange_id)
        if not exchange:
            return jsonify({"error": "Exchange not found"}), 404
            
        request_obj = exchange.request
        listing = exchange.listing
        if not request_obj or not listing:
            return jsonify({"error": "Exchange details not found"}), 404
        if current_user.id not in [request_obj.learner_id, listing.user_id]:
            return jsonify({"error": "Unauthorized"}), 403
            
        # Update user activity timestamp in database
        from app.database import Database
        db = Database()
        try:
            db.execute("UPDATE users SET last_active_at = %s WHERE id = %s", (datetime.utcnow(), current_user.id))
        finally:
            db.close()
            
        other_user = listing.user if current_user.id == request_obj.learner_id else request_obj.learner
        other_user_db = User.find_by_id(other_user.id)
        
        return jsonify({
            "other_online": other_user_db.is_online if other_user_db else False,
            "video_call_active": exchange.video_call_active,
            "summary": exchange.video_session_summary
        })

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
        
        request_obj = ExchangeRequestRepository().create(
            listing_id=listing_id,
            learner_id=current_user.id,
            offered_skill_id=offered_skill_id,
            requested_message=requested_message,
        )
        if listing.exchange_type == "credit":
            from app.repositories.credit_repository import CreditRepository
            CreditRepository().create_hold(current_user.id, request_obj.id, listing.credit_cost)
            
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
        if listing.exchange_type == "credit":
            from app.repositories.credit_repository import CreditRepository
            CreditRepository().release_hold(request_id)

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
        from app.repositories.credit_repository import CreditRepository
        CreditRepository().release_hold(request_id)
        
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

        # Check active exchange & online status of participants
        from app.repositories import ExchangeRepository, UserRepository
        active_exchange = None
        both_online = False
        other_participant = conversation.other_participant(current_user.id)
        if other_participant:
            active_exchange = ExchangeRepository().find_active_between_users(current_user.id, other_participant.id)
            if active_exchange:
                me = UserRepository().find_by_id(current_user.id)
                other = UserRepository().find_by_id(other_participant.id)
                both_online = me.is_online and other.is_online

        return self.render(
            "messages/detail.html",
            conversation=conversation,
            conversations=conversations,
            ordered_messages=conversation.messages,
            form=MessageShellForm(),
            active_exchange=active_exchange,
            both_online=both_online,
        )

    @login_required
    def notifications(self):
        items = self._notification_service.list_for_user(current_user.id, limit=50)
        return self.render("notifications/index.html", notifications=items)

    @login_required
    def notification_counts(self):
        return jsonify(
            {
                "messages": self._message_service.count_unread(current_user.id),
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

    REVIEWS_PER_PAGE = 10

    def user_reviews(self, user_id: int):
        page = request.args.get("page", 1, type=int) or 1
        page = max(page, 1)
        try:
            review_user, reviews, total = self._profile_service.get_review_history(
                user_id, page=page, per_page=self.REVIEWS_PER_PAGE
            )
        except ProfileNotFoundError:
            abort(404)
        total_pages = max(1, -(-total // self.REVIEWS_PER_PAGE))
        return self.render(
            "reviews/user_reviews.html",
            review_user=review_user,
            reviews=reviews,
            page=page,
            total_pages=total_pages,
            total_reviews=total,
        )

    @login_required
    def review_form(self, exchange_id: int):
        from app.repositories import ProfileReviewRepository

        exchange = ExchangeRepository().find_by_id(exchange_id)
        if not exchange:
            abort(404)
        request_obj = exchange.request
        listing = request_obj.listing if request_obj else None
        if not request_obj or not listing:
            abort(404)
        if current_user.id not in [request_obj.learner_id, listing.user_id]:
            abort(403)
        if exchange.status != "completed":
            flash("Reviews unlock after both parties mark the exchange complete.", "warning")
            return redirect(url_for("exchanges.detail", exchange_id=exchange_id))

        review_repo = ProfileReviewRepository()
        if review_repo.find_by_exchange_and_reviewer(exchange.id, current_user.id):
            flash("You have already reviewed this exchange.", "info")
            return redirect(url_for("exchanges.detail", exchange_id=exchange_id))

        reviewee_id = listing.user_id if current_user.id == request_obj.learner_id else request_obj.learner_id
        reviewee = User.find_by_id(reviewee_id)
        if not reviewee:
            abort(404)

        form = ReviewShellForm()
        if request.method == "POST":
            rating_raw = request.form.get("rating", "").strip()
            comment = request.form.get("comment", "").strip()
            error = None
            if not rating_raw.isdigit() or not 1 <= int(rating_raw) <= 5:
                error = "Please choose a star rating between 1 and 5."
            elif len(comment) > 500:
                error = "Review comments are limited to 500 characters."
            if error:
                flash(error, "danger")
                form = ReviewShellForm(rating=rating_raw, comment=comment)
            else:
                review_repo.create(
                    reviewee_user_id=reviewee_id,
                    reviewer_id=current_user.id,
                    reviewer_name=current_user.full_name,
                    rating=int(rating_raw),
                    comment=comment or None,
                    exchange_id=exchange.id,
                )
                self._notification_service.notify_new_review(
                    user_id=reviewee_id,
                    reviewer_name=current_user.full_name,
                    target_url=url_for("reviews.user_reviews", user_id=reviewee_id),
                )
                flash("Your review has been published.", "success")
                return redirect(url_for("exchanges.detail", exchange_id=exchange_id))

        return self.render("reviews/form.html", form=form, exchange=exchange, reviewee=reviewee)

    def frontend_only_action(self, *args, **kwargs):
        flash("This action is frontend-only in the current project scope.", "info")
        return redirect(request.referrer or url_for("main.dashboard"))

    @login_required
    def delete_account(self):
        user = User.find_by_id(current_user.id)
        if not user:
            abort(404)
        if request.method == "POST":
            password = request.form.get("password")
            if not password or not user.check_password(password):
                flash("Incorrect password confirmation.", "danger")
                return redirect(url_for("profile.edit"))
            
            # Perform deletion/anonymization
            self._profile_service.delete_account(user.id)
            
            # Log out the user
            from flask_login import logout_user
            logout_user()
            
            # Clean session
            session.pop("csrf_token", None)
            
            flash("Your account has been deleted successfully. A final confirmation email has been sent.", "success")
            return redirect(url_for("auth.login"))
            
        return redirect(url_for("profile.edit"))


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
            ("5", "5 - Excellent"),
            ("4", "4 - Good"),
            ("3", "3 - Okay"),
            ("2", "2 - Poor"),
            ("1", "1 - Very poor"),
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
