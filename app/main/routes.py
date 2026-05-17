from __future__ import annotations

from pathlib import Path

from flask import current_app, render_template, send_from_directory
from flask_login import login_required

from ..models import Exchange, Listing, Notification, Profile, Review
from . import main_bp


@main_bp.route("/")
def home():
    recent_listings = Listing.query.filter_by(status="approved").order_by(Listing.created_at.desc()).limit(6).all()
    top_profiles = (
        Profile.query.filter(Profile.review_count >= 3)
        .order_by(Profile.reputation_score.desc(), Profile.completed_exchange_count.desc())
        .limit(5)
        .all()
    )
    stats = {
        "listings": Listing.query.filter_by(status="approved").count(),
        "exchanges": Exchange.query.count(),
        "reviews": Review.query.count(),
        "members": Profile.query.count(),
    }
    return render_template(
        "main/home.html",
        recent_listings=recent_listings,
        top_profiles=top_profiles,
        stats=stats,
    )


@main_bp.route("/dashboard")
@login_required
def dashboard():
    from flask_login import current_user

    my_listings = current_user.listings.order_by(Listing.updated_at.desc()).limit(5).all()
    pending_requests = current_user.received_requests.filter_by(status="pending").limit(5).all()
    exchanges = (
        Exchange.query.filter(
            (Exchange.teacher_id == current_user.id) | (Exchange.learner_id == current_user.id)
        )
        .order_by(Exchange.created_at.desc())
        .limit(5)
        .all()
    )
    notifications = current_user.notifications.order_by(Notification.created_at.desc()).limit(5).all()
    return render_template(
        "main/dashboard.html",
        my_listings=my_listings,
        pending_requests=pending_requests,
        exchanges=exchanges,
        notifications=notifications,
    )


@main_bp.route("/media/<path:filename>")
def media(filename: str):
    return send_from_directory(Path(current_app.config["UPLOAD_FOLDER"]), filename)
