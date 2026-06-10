from __future__ import annotations

from pathlib import Path

from flask import current_app, send_from_directory
from flask_login import current_user, login_required

from app.services import ExchangeHistoryService, NotificationService

from .base_controller import BaseController


class MainController(BaseController):
    def __init__(
        self,
        notification_service: NotificationService | None = None,
        exchange_history_service: ExchangeHistoryService | None = None,
    ):
        self._notification_service = notification_service
        self._exchange_history_service = exchange_history_service

    def home(self):
        stats = {
            "listings": 0,
            "exchanges": 0,
            "reviews": 0,
            "members": 0,
        }
        return self.render("main/home.html", stats=stats, recent_listings=[], top_profiles=[])

    @login_required
    def dashboard(self):
        notifications = []
        unread_notification_count = 0
        exchanges = []
        exchange_count = 0
        if self._notification_service:
            notifications = self._notification_service.list_for_user(current_user.id, limit=5)
            unread_notification_count = self._notification_service.unread_count(current_user.id)
        if self._exchange_history_service:
            exchanges = self._exchange_history_service.list_for_user(current_user.id, limit=5)
            exchange_count = self._exchange_history_service.count_for_user(current_user.id)
        return self.render(
            "main/dashboard.html",
            my_listings=[],
            pending_requests=[],
            exchanges=exchanges,
            exchange_count=exchange_count,
            notifications=notifications,
            unread_notification_count=unread_notification_count,
        )

    def media(self, filename: str):
        return send_from_directory(Path(current_app.config["UPLOAD_FOLDER"]), filename)
