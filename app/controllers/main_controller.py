from __future__ import annotations

from pathlib import Path

from flask import current_app, send_from_directory
from flask_login import login_required

from app.services.listing_catalog import all_listings

from .base_controller import BaseController


class MainController(BaseController):
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
        return self.render(
            "main/dashboard.html",
            my_listings=[],
            pending_requests=[],
            exchanges=[],
            notifications=[],
        )

    def media(self, filename: str):
        return send_from_directory(Path(current_app.config["UPLOAD_FOLDER"]), filename)
