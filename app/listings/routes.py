from __future__ import annotations

from math import ceil

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..forms import ExchangeRequestForm, ListingForm
from ..models import Category, Listing, ListingAvailability, Skill
from ..services import distance_km
from . import listings_bp


def _apply_listing_filters(listings: list[Listing]) -> list[Listing]:
    query = request.args.get("q", "").strip().lower()
    category_ids = {int(value) for value in request.args.getlist("category") if value.isdigit()}
    radius_value = request.args.get("radius")
    filtered = listings
    if query:
        tokens = [token for token in query.split() if token]
        filtered = [
            listing
            for listing in filtered
            if all(
                token in " ".join(
                    [
                        listing.title.lower(),
                        listing.description.lower(),
                        listing.skill.name.lower(),
                        listing.category.name.lower(),
                    ]
                )
                for token in tokens
            )
        ]
    if category_ids:
        filtered = [listing for listing in filtered if listing.category_id in category_ids]
    if radius_value and radius_value.isdigit() and current_user.is_authenticated and current_user.profile:
        if current_user.profile.latitude is not None and current_user.profile.longitude is not None:
            radius = float(radius_value)
            filtered = [
                listing
                for listing in filtered
                if listing.user.profile
                and listing.user.profile.latitude is not None
                and listing.user.profile.longitude is not None
                and distance_km(
                    current_user.profile.latitude,
                    current_user.profile.longitude,
                    listing.user.profile.latitude,
                    listing.user.profile.longitude,
                )
                <= radius
            ]
    return filtered


def _paginate(items: list, page: int, per_page: int) -> tuple[list, int]:
    total_pages = max(1, ceil(len(items) / per_page)) if items else 1
    start = (page - 1) * per_page
    end = start + per_page
    return items[start:end], total_pages


def _listing_form_choices(form: ListingForm) -> None:
    form.category_id.choices = [(item.id, item.name) for item in Category.query.order_by(Category.name).all()]
    form.skill_id.choices = [(item.id, item.name) for item in Skill.query.order_by(Skill.name).all()]


def _save_availability(listing: Listing, raw_text: str | None) -> None:
    listing.availability.clear()
    for line in (raw_text or "").splitlines():
        clean = line.strip()
        if clean:
            listing.availability.append(ListingAvailability(label=clean, is_remote="remote" in clean.lower()))


@listings_bp.route("/")
def index():
    page = max(1, int(request.args.get("page", 1)))
    all_listings = Listing.query.filter_by(status="approved").order_by(Listing.created_at.desc()).all()
    filtered = _apply_listing_filters(all_listings)
    page_items, total_pages = _paginate(filtered, page, current_app.config["PAGINATION_PER_PAGE"])
    categories = Category.query.order_by(Category.name).all()
    return render_template(
        "listings/index.html",
        listings=page_items,
        categories=categories,
        page=page,
        total_pages=total_pages,
        total_results=len(filtered),
    )


@listings_bp.route("/api/search")
def api_search():
    all_listings = Listing.query.filter_by(status="approved").order_by(Listing.created_at.desc()).all()
    filtered = _apply_listing_filters(all_listings)
    html = render_template("partials/listing_cards.html", listings=filtered[:20])
    return jsonify({"count": len(filtered), "html": html})


@listings_bp.route("/mine")
@login_required
def mine():
    items = current_user.listings.order_by(Listing.updated_at.desc()).all()
    return render_template("listings/mine.html", listings=items)


@listings_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    form = ListingForm()
    _listing_form_choices(form)
    if form.validate_on_submit():
        listing = Listing(
            user=current_user,
            title=form.title.data.strip(),
            skill_id=form.skill_id.data,
            category_id=form.category_id.data,
            description=form.description.data.strip(),
            exchange_type=form.exchange_type.data,
            min_credits=form.min_credits.data or 0,
            location_text=form.location_text.data,
            contact_method=form.contact_method.data,
            status="pending",
        )
        _save_availability(listing, form.availability_labels.data)
        db.session.add(listing)
        db.session.commit()
        flash("Listing submitted for admin review.", "success")
        return redirect(url_for("listings.mine"))
    return render_template("listings/form.html", form=form, title="Create listing")


@listings_bp.route("/<int:listing_id>")
def detail(listing_id: int):
    listing = Listing.query.get_or_404(listing_id)
    can_preview = current_user.is_authenticated and (current_user.id == listing.user_id or current_user.is_admin)
    if listing.status != "approved" and not can_preview:
        abort(404)
    request_form = ExchangeRequestForm()
    if current_user.is_authenticated:
        request_form.offered_skill_id.choices = [(0, "Select skill")] + [
            (item.skill_id, item.skill.name) for item in current_user.offered_skills
        ]
    else:
        request_form.offered_skill_id.choices = [(0, "Select skill")]
    return render_template("listings/detail.html", listing=listing, request_form=request_form)


@listings_bp.route("/<int:listing_id>/edit", methods=["GET", "POST"])
@login_required
def edit(listing_id: int):
    listing = Listing.query.get_or_404(listing_id)
    if listing.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    form = ListingForm(obj=listing)
    _listing_form_choices(form)
    if request.method == "GET":
        form.availability_labels.data = "\n".join(item.label for item in listing.availability)
    if form.validate_on_submit():
        listing.title = form.title.data.strip()
        listing.skill_id = form.skill_id.data
        listing.category_id = form.category_id.data
        listing.description = form.description.data.strip()
        listing.exchange_type = form.exchange_type.data
        listing.min_credits = form.min_credits.data or 0
        listing.location_text = form.location_text.data
        listing.contact_method = form.contact_method.data
        listing.status = "pending" if not current_user.is_admin else listing.status
        listing.rejection_reason = None
        _save_availability(listing, form.availability_labels.data)
        db.session.commit()
        flash("Listing updated.", "success")
        return redirect(url_for("listings.detail", listing_id=listing.id))
    return render_template("listings/form.html", form=form, title="Edit listing")


@listings_bp.route("/<int:listing_id>/delete", methods=["POST"])
@login_required
def delete(listing_id: int):
    listing = Listing.query.get_or_404(listing_id)
    if listing.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    db.session.delete(listing)
    db.session.commit()
    flash("Listing deleted.", "info")
    return redirect(url_for("listings.mine"))
