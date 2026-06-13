from __future__ import annotations

from pathlib import Path

from flask import current_app, send_from_directory
from flask_login import current_user, login_required

from app.repositories import (
    CategoryRepository,
    ExchangeRepository,
    ExchangeRequestRepository,
    ProfileRepository,
    ProfileReviewRepository,
    SkillRepository,
    UserRepository,
)
from app.services import NotificationService, SkillService

from .base_controller import BaseController


class MainController(BaseController):
    def __init__(self, notification_service: NotificationService | None = None):
        self._notification_service = notification_service or NotificationService()
        self._skill_service = SkillService(SkillRepository(), CategoryRepository())

    def home(self):
        listings = self._skill_service.search_listings(status="approved")
        stats = {
            "listings": len(listings),
            "exchanges": ExchangeRepository().count(),
            "reviews": ProfileReviewRepository().count_all(),
            "members": UserRepository().count(),
        }
        return self.render(
            "main/home.html",
            stats=stats,
            recent_listings=listings[:3],
            top_profiles=ProfileRepository().top_rated(3),
        )

    @login_required
    def dashboard(self):
        recent_notifications = self._notification_service.list_for_user(
            current_user.id, limit=5
        )
        return self.render(
            "main/dashboard.html",
            my_listings=self._skill_service.get_listings_by_user(current_user.id),
            pending_requests=ExchangeRequestRepository().list_incoming_pending(current_user.id),
            exchanges=ExchangeRepository().list_for_user(current_user.id, status="active"),
            notifications=recent_notifications,
            unread_notification_count=self._notification_service.unread_count(current_user.id),
        )

    def media(self, filename: str):
        return send_from_directory(Path(current_app.config["UPLOAD_FOLDER"]), filename)
