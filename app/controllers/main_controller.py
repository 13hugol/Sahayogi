from __future__ import annotations

from pathlib import Path

from flask import current_app, send_from_directory
from flask_login import current_user, login_required

from app.services import NotificationService
from app.services.listing_catalog import all_listings

from .base_controller import BaseController


class MainController(BaseController):
    def __init__(self, notification_service: NotificationService | None = None):
        self._notification_service = notification_service or NotificationService()

    def home(self):
        listings = all_listings()
        stats = {
            "listings": len(listings),
            "exchanges": 0,
            "reviews": 0,
            "members": 0,
        }
        return self.render("main/home.html", stats=stats, recent_listings=listings[:3], top_profiles=[])

    @login_required
    def dashboard(self):
        recent_notifications = self._notification_service.list_for_user(
            current_user.id, limit=5
        )
        return self.render(
            "main/dashboard.html",
            my_listings=[],
            pending_requests=[],
            exchanges=[],
            notifications=recent_notifications,
        )

    def media(self, filename: str):
        return send_from_directory(Path(current_app.config["UPLOAD_FOLDER"]), filename)
