from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..forms import ExchangeRequestForm
from ..models import Exchange, ExchangeRequest, Listing, Skill, utcnow
from ..services import (
    create_notification,
    get_or_create_conversation,
    release_hold,
    reserve_credits,
)
from . import requests_bp


@requests_bp.route("/create/<int:listing_id>", methods=["POST"])
@login_required
def create(listing_id: int):
    listing = Listing.query.get_or_404(listing_id)
    if listing.user_id == current_user.id:
        abort(400)
    if listing.status != "approved":
        abort(404)
    form = ExchangeRequestForm()
    form.offered_skill_id.choices = [(0, "Select skill")] + [
        (item.skill_id, item.skill.name) for item in current_user.offered_skills
    ]
    if not form.validate_on_submit():
        flash("Please correct the request form.", "danger")
        return redirect(url_for("listings.detail", listing_id=listing_id))
    offered_skill_id = form.offered_skill_id.data or None
    if listing.exchange_type == "teach" and not offered_skill_id:
        flash("Choose a skill to barter for a teaching exchange.", "warning")
        return redirect(url_for("listings.detail", listing_id=listing_id))
    credits_reserved = listing.min_credits if listing.exchange_type == "credit" else 0
    exchange_request = ExchangeRequest(
        listing=listing,
        sender=current_user,
        recipient=listing.user,
        request_type=listing.exchange_type,
        offered_skill_id=offered_skill_id,
        requested_message=form.requested_message.data,
        credits_reserved=credits_reserved,
    )
    db.session.add(exchange_request)
    db.session.flush()
    if listing.exchange_type == "credit":
        try:
            reserve_credits(current_user, exchange_request.id, credits_reserved)
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return redirect(url_for("listings.detail", listing_id=listing_id))
    create_notification(
        listing.user,
        "New exchange request",
        f"{current_user.full_name} requested your listing '{listing.title}'.",
        url_for("requests_bp.inbox"),
        "info",
    )
    db.session.commit()
    flash("Request submitted.", "success")
    return redirect(url_for("requests_bp.sent"))


@requests_bp.route("/inbox")
@login_required
def inbox():
    pending = current_user.received_requests.filter_by(status="pending").order_by(ExchangeRequest.created_at.desc()).all()
    history = current_user.received_requests.filter(ExchangeRequest.status != "pending").order_by(ExchangeRequest.created_at.desc()).all()
    return render_template("requests/inbox.html", pending_requests=pending, history=history)


@requests_bp.route("/sent")
@login_required
def sent():
    items = current_user.sent_requests.order_by(ExchangeRequest.created_at.desc()).all()
    return render_template("requests/sent.html", requests=items)


@requests_bp.route("/<int:request_id>/accept", methods=["POST"])
@login_required
def accept(request_id: int):
    exchange_request = ExchangeRequest.query.get_or_404(request_id)
    if exchange_request.recipient_id != current_user.id:
        abort(403)
    if exchange_request.status != "pending":
        flash("That request has already been processed.", "warning")
        return redirect(url_for("requests_bp.inbox"))
    exchange_request.status = "accepted"
    exchange_request.responded_at = utcnow()
    exchange = Exchange(
        request=exchange_request,
        listing=exchange_request.listing,
        teacher=exchange_request.recipient,
        learner=exchange_request.sender,
        barter_skill_id=exchange_request.offered_skill_id,
        exchange_type=exchange_request.request_type,
    )
    db.session.add(exchange)
    db.session.flush()
    get_or_create_conversation(
        exchange.teacher_id,
        exchange.learner_id,
        subject=f"Exchange #{exchange.id}: {exchange.listing.title}",
        exchange=exchange,
    )
    create_notification(
        exchange_request.sender,
        "Request accepted",
        f"Your request for '{exchange_request.listing.title}' was accepted.",
        url_for("exchanges.detail", exchange_id=exchange.id),
        "success",
    )
    db.session.commit()
    flash("Request accepted and exchange opened.", "success")
    return redirect(url_for("exchanges.detail", exchange_id=exchange.id))


@requests_bp.route("/<int:request_id>/decline", methods=["POST"])
@login_required
def decline(request_id: int):
    exchange_request = ExchangeRequest.query.get_or_404(request_id)
    if exchange_request.recipient_id != current_user.id:
        abort(403)
    if exchange_request.status != "pending":
        flash("That request has already been processed.", "warning")
        return redirect(url_for("requests_bp.inbox"))
    exchange_request.status = "declined"
    exchange_request.responded_at = utcnow()
    release_hold(exchange_request.credit_hold)
    create_notification(
        exchange_request.sender,
        "Request declined",
        f"Your request for '{exchange_request.listing.title}' was declined.",
        url_for("requests_bp.sent"),
        "warning",
    )
    db.session.commit()
    flash("Request declined.", "info")
    return redirect(url_for("requests_bp.inbox"))


@requests_bp.route("/<int:request_id>/cancel", methods=["POST"])
@login_required
def cancel(request_id: int):
    exchange_request = ExchangeRequest.query.get_or_404(request_id)
    if exchange_request.sender_id != current_user.id:
        abort(403)
    if exchange_request.status != "pending":
        flash("Only pending requests can be cancelled.", "warning")
        return redirect(url_for("requests_bp.sent"))
    exchange_request.status = "cancelled"
    exchange_request.responded_at = utcnow()
    release_hold(exchange_request.credit_hold)
    create_notification(
        exchange_request.recipient,
        "Request cancelled",
        f"{current_user.full_name} cancelled a request for '{exchange_request.listing.title}'.",
        url_for("requests_bp.inbox"),
        "warning",
    )
    db.session.commit()
    flash("Request cancelled.", "info")
    return redirect(url_for("requests_bp.sent"))
