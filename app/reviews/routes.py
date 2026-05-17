from __future__ import annotations

from flask import abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..forms import ReviewForm
from ..models import Exchange, Profile, Review, User
from ..services import create_notification, recalculate_reputation, review_allowed
from . import reviews_bp


@reviews_bp.route("/exchange/<int:exchange_id>", methods=["GET", "POST"])
@login_required
def create(exchange_id: int):
    exchange = Exchange.query.get_or_404(exchange_id)
    if not review_allowed(exchange, current_user.id):
        abort(403)
    reviewee = exchange.teacher if exchange.learner_id == current_user.id else exchange.learner
    form = ReviewForm()
    if form.validate_on_submit():
        review = Review(
            exchange=exchange,
            reviewer=current_user,
            reviewee=reviewee,
            rating=form.rating.data,
            comment=form.comment.data,
        )
        db.session.add(review)
        recalculate_reputation(reviewee)
        create_notification(
            reviewee,
            "New review received",
            f"{current_user.full_name} left a review on your profile.",
            url_for("reviews.user_reviews", user_id=reviewee.id),
            "success",
        )
        db.session.commit()
        flash("Review published.", "success")
        return redirect(url_for("exchanges.detail", exchange_id=exchange.id))
    return render_template("reviews/form.html", form=form, exchange=exchange, reviewee=reviewee)


@reviews_bp.route("/user/<int:user_id>")
def user_reviews(user_id: int):
    user = User.query.get_or_404(user_id)
    reviews = Review.query.filter_by(reviewee_id=user.id).order_by(Review.created_at.desc()).all()
    return render_template("reviews/user_reviews.html", review_user=user, reviews=reviews)


@reviews_bp.route("/top-rated")
def top_rated():
    profiles = (
        Profile.query.filter(Profile.review_count >= 3)
        .order_by(Profile.reputation_score.desc(), Profile.completed_exchange_count.desc())
        .all()
    )
    return render_template("reviews/top_rated.html", profiles=profiles)
