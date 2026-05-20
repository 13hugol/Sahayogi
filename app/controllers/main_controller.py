from __future__ import annotations

from pathlib import Path

from flask import current_app, render_template, send_from_directory
from flask_login import login_required

from .base_controller import BaseController


class MainController(BaseController):
    def home(self):
        stats = {
            "listings": 0,
            "exchanges": 0,
            "reviews": 0,
            "members": 0,
        }
        return render_template("main/home.html", stats=stats, recent_listings=[], top_profiles=[])

    @login_required
    def dashboard(self):
        return render_template(
            "main/dashboard.html",
            my_listings=[],
            pending_requests=[],
            exchanges=[],
            notifications=[],
        )

    def media(self, filename: str):
        return send_from_directory(Path(current_app.config["UPLOAD_FOLDER"]), filename)
