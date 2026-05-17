from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Exchange, Review
from ..services import complete_exchange, review_allowed
from . import exchanges_bp


def _user_exchange_query():
    return Exchange.query.filter(
        (Exchange.teacher_id == current_user.id) | (Exchange.learner_id == current_user.id)
    ).order_by(Exchange.created_at.desc())


@exchanges_bp.route("/")
@login_required
def index():
    status = request.args.get("status")
    query = _user_exchange_query()
    if status:
        query = query.filter_by(status=status)
    exchanges = query.all()
    return render_template("exchanges/index.html", exchanges=exchanges, selected_status=status)


@exchanges_bp.route("/<int:exchange_id>")
@login_required
def detail(exchange_id: int):
    exchange = Exchange.query.get_or_404(exchange_id)
    if current_user.id not in {exchange.teacher_id, exchange.learner_id} and not current_user.is_admin:
        abort(403)
    current_mark_ids = {mark.user_id for mark in exchange.completion_marks}
    can_mark_complete = exchange.status == "active" and current_user.id not in current_mark_ids
    can_review = review_allowed(exchange, current_user.id)
    reviews = exchange.reviews.order_by(Review.created_at.desc()).all()
    return render_template(
        "exchanges/detail.html",
        exchange=exchange,
        can_mark_complete=can_mark_complete,
        can_review=can_review,
        reviews=reviews,
    )


@exchanges_bp.route("/<int:exchange_id>/complete", methods=["POST"])
@login_required
def mark_complete(exchange_id: int):
    exchange = Exchange.query.get_or_404(exchange_id)
    if current_user.id not in {exchange.teacher_id, exchange.learner_id}:
        abort(403)
    if exchange.status != "active":
        flash("This exchange is not active.", "warning")
        return redirect(url_for("exchanges.detail", exchange_id=exchange_id))
    changed = complete_exchange(exchange, current_user)
    db.session.commit()
    if changed:
        flash("Completion status recorded.", "success")
    else:
        flash("You already marked this exchange complete.", "info")
    return redirect(url_for("exchanges.detail", exchange_id=exchange_id))
