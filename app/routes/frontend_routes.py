from __future__ import annotations

from flask import Blueprint

from ..controllers.frontend_controller import FrontendController
from ..repositories import (
    ProfileCertificateRepository,
    ProfileRepository,
    ProfileReviewRepository,
    RoleRepository,
    UserRepository,
)
from ..services import ProfileService


class FrontendRoutes:
    def __init__(self):
        profile_repository = ProfileRepository()
        role_repository = RoleRepository()
        user_repository = UserRepository(
            role_repository=role_repository,
            profile_repository=profile_repository,
        )
        self.controller = FrontendController(
            ProfileService(
                user_repository,
                profile_repository,
                ProfileCertificateRepository(),
                ProfileReviewRepository(),
            )
        )

    def register(self):
        listings = Blueprint("listings", __name__, url_prefix="/listings")
        listings.route("/", endpoint="index")(self.controller.marketplace)
        listings.route("/api/search", endpoint="api_search")(self.controller.api_search)
        listings.route("/create", methods=["GET", "POST"], endpoint="create")(self.controller.post_listing)
        listings.route("/mine", endpoint="mine")(self.controller.my_listings)
        listings.route("/saved", endpoint="saved")(self.controller.saved_listings)
        listings.route("/<int:listing_id>/save", methods=["POST"], endpoint="save")(self.controller.save_listing)
        listings.route("/<int:listing_id>/unsave", methods=["POST"], endpoint="unsave")(self.controller.unsave_listing)
        listings.route("/<int:listing_id>", endpoint="detail")(self.controller.listing_detail)
        listings.route("/<int:listing_id>/edit", methods=["GET", "POST"], endpoint="edit")(self.controller.post_listing)
        listings.route("/<int:listing_id>/delete", methods=["POST"], endpoint="delete")(self.controller.frontend_only_action)

        credits = Blueprint("credits", __name__, url_prefix="/credits")
        credits.route("/ledger", endpoint="ledger")(self.controller.wallet)

        matches = Blueprint("matches", __name__, url_prefix="/matches")
        matches.route("/", endpoint="index")(self.controller.matches)

        requests_bp = Blueprint("requests_bp", __name__, url_prefix="/requests")
        requests_bp.route("/inbox", endpoint="inbox")(self.controller.requests)
        requests_bp.route("/sent", endpoint="sent")(self.controller.sent_requests)
        requests_bp.route("/create/<int:listing_id>", methods=["POST"], endpoint="create")(self.controller.frontend_only_action)
        requests_bp.route("/<int:request_id>/accept", methods=["POST"], endpoint="accept")(self.controller.frontend_only_action)
        requests_bp.route("/<int:request_id>/decline", methods=["POST"], endpoint="decline")(self.controller.frontend_only_action)
        requests_bp.route("/<int:request_id>/cancel", methods=["POST"], endpoint="cancel")(self.controller.frontend_only_action)

        exchanges = Blueprint("exchanges", __name__, url_prefix="/exchanges")
        exchanges.route("/", endpoint="index")(self.controller.exchanges)
        exchanges.route("/<int:exchange_id>", endpoint="detail")(self.controller.exchange_detail)
        exchanges.route("/<int:exchange_id>/complete", methods=["POST"], endpoint="mark_complete")(self.controller.frontend_only_action)

        messages = Blueprint("messages", __name__, url_prefix="/messages")
        messages.route("/", endpoint="index")(self.controller.messages)
        messages.route("/<int:conversation_id>", endpoint="detail")(self.controller.conversation)

        notifications = Blueprint("notifications", __name__, url_prefix="/notifications")
        notifications.route("/", endpoint="index")(self.controller.notifications)
        notifications.route("/counts", endpoint="counts")(self.controller.notification_counts)
        notifications.route("/mark-all-read", methods=["POST"], endpoint="mark_all_read")(self.controller.frontend_only_action)
        notifications.route("/<int:notification_id>", endpoint="open_item")(self.controller.frontend_only_action)

        profile = Blueprint("profile", __name__)
        profile.route("/profile/me", endpoint="me")(self.controller.profile_me)
        profile.route("/profile/edit", endpoint="edit")(self.controller.profile_edit)
        profile.route("/profile/certificates", endpoint="certificates")(self.controller.certificates)
        profile.route("/profile/delete", methods=["POST"], endpoint="delete_account")(self.controller.frontend_only_action)
        profile.route("/users/<int:user_id>", endpoint="view")(self.controller.profile_view)
        profile.route("/users/<int:user_id>/report", methods=["GET", "POST"], endpoint="report")(self.controller.report_user)

        reviews = Blueprint("reviews", __name__, url_prefix="/reviews")
        reviews.route("/top-rated", endpoint="top_rated")(self.controller.top_rated)
        reviews.route("/users/<int:user_id>", endpoint="user_reviews")(self.controller.user_reviews)
        reviews.route("/exchange/<int:exchange_id>", methods=["GET", "POST"], endpoint="create")(self.controller.review_form)

        return [
            listings,
            credits,
            matches,
            requests_bp,
            exchanges,
            messages,
            notifications,
            profile,
            reviews,
        ]
