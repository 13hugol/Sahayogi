from __future__ import annotations

from datetime import timedelta

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..decorators import admin_required
from ..extensions import db
from ..forms import CategoryForm, SkillForm, SuspensionForm
from ..models import Category, Certificate, Listing, Report, Role, Skill, User, utcnow
from ..services import audit, create_notification
from . import admin_bp


@admin_bp.route("/")
@admin_required
def dashboard():
    stats = {
        "pending_listings": Listing.query.filter_by(status="pending").count(),
        "pending_certificates": Certificate.query.filter_by(status="pending").count(),
        "open_reports": Report.query.filter_by(status="open").count(),
        "users": User.query.count(),
    }
    return render_template("admin/dashboard.html", stats=stats)


@admin_bp.route("/listings")
@admin_required
def listings():
    pending = Listing.query.filter_by(status="pending").order_by(Listing.created_at.asc()).all()
    return render_template("admin/listings.html", listings=pending)


@admin_bp.route("/listings/<int:listing_id>/approve", methods=["POST"])
@admin_required
def approve_listing(listing_id: int):
    listing = Listing.query.get_or_404(listing_id)
    listing.status = "approved"
    listing.approved_at = utcnow()
    listing.reviewer = current_user
    listing.rejection_reason = None
    create_notification(
        listing.user,
        "Listing approved",
        f"Your listing '{listing.title}' is now live.",
        url_for("listings.detail", listing_id=listing.id),
        "success",
    )
    audit("approve_listing", "Listing", listing.id, listing.title)
    db.session.commit()
    flash("Listing approved.", "success")
    return redirect(url_for("admin.listings"))


@admin_bp.route("/listings/<int:listing_id>/reject", methods=["POST"])
@admin_required
def reject_listing(listing_id: int):
    listing = Listing.query.get_or_404(listing_id)
    reason = request.form.get("reason", "").strip() or "Quality review not passed."
    listing.status = "rejected"
    listing.reviewer = current_user
    listing.rejection_reason = reason
    create_notification(
        listing.user,
        "Listing rejected",
        f"Your listing '{listing.title}' was rejected: {reason}",
        url_for("listings.mine"),
        "warning",
    )
    audit("reject_listing", "Listing", listing.id, reason)
    db.session.commit()
    flash("Listing rejected.", "info")
    return redirect(url_for("admin.listings"))


@admin_bp.route("/certificates")
@admin_required
def certificates():
    pending = Certificate.query.filter_by(status="pending").order_by(Certificate.created_at.asc()).all()
    return render_template("admin/certificates.html", certificates=pending)


@admin_bp.route("/certificates/<int:certificate_id>/approve", methods=["POST"])
@admin_required
def approve_certificate(certificate_id: int):
    certificate = Certificate.query.get_or_404(certificate_id)
    certificate.status = "approved"
    certificate.reviewer = current_user
    certificate.reviewed_at = utcnow()
    certificate.review_notes = request.form.get("notes", "").strip() or None
    create_notification(
        certificate.user,
        "Certificate approved",
        f"Your certificate for {certificate.skill.name} has been approved.",
        url_for("profile.view", user_id=certificate.user_id),
        "success",
    )
    audit("approve_certificate", "Certificate", certificate.id, certificate.skill.name)
    db.session.commit()
    flash("Certificate approved.", "success")
    return redirect(url_for("admin.certificates"))


@admin_bp.route("/certificates/<int:certificate_id>/reject", methods=["POST"])
@admin_required
def reject_certificate(certificate_id: int):
    certificate = Certificate.query.get_or_404(certificate_id)
    notes = request.form.get("notes", "").strip() or "Evidence could not be verified."
    certificate.status = "rejected"
    certificate.reviewer = current_user
    certificate.reviewed_at = utcnow()
    certificate.review_notes = notes
    create_notification(
        certificate.user,
        "Certificate rejected",
        f"Your certificate for {certificate.skill.name} was rejected: {notes}",
        url_for("profile.certificates"),
        "warning",
    )
    audit("reject_certificate", "Certificate", certificate.id, notes)
    db.session.commit()
    flash("Certificate rejected.", "info")
    return redirect(url_for("admin.certificates"))


@admin_bp.route("/reports")
@admin_required
def reports():
    items = Report.query.order_by(Report.created_at.desc()).all()
    return render_template("admin/reports.html", reports=items)


@admin_bp.route("/reports/<int:report_id>/<string:decision>", methods=["POST"])
@admin_required
def resolve_report(report_id: int, decision: str):
    report = Report.query.get_or_404(report_id)
    if decision not in {"resolved", "dismissed"}:
        abort(400)
    report.status = decision
    report.resolved_at = utcnow()
    audit("resolve_report", "Report", report.id, decision)
    db.session.commit()
    flash(f"Report marked {decision}.", "success")
    return redirect(url_for("admin.reports"))


@admin_bp.route("/users", methods=["GET", "POST"])
@admin_required
def users():
    target_id = request.args.get("user_id", type=int)
    form = SuspensionForm()
    users = User.query.order_by(User.created_at.desc()).all()
    target_user = User.query.get(target_id) if target_id else None
    if target_user:
        if request.method == "GET":
            form.action.data = "activate" if target_user.status == "active" else target_user.status
        if form.validate_on_submit():
            if form.action.data == "ban":
                target_user.status = "banned"
                target_user.suspended_until = None
                detail = "User permanently banned."
            elif form.action.data == "suspend":
                target_user.status = "suspended"
                target_user.suspended_until = utcnow() + timedelta(days=form.days.data or 1)
                detail = f"User suspended for {form.days.data or 1} days."
            else:
                target_user.status = "active"
                target_user.suspended_until = None
                detail = "User re-activated."
            create_notification(
                target_user,
                "Account status updated",
                form.reason.data or detail,
                url_for("main.home"),
                "warning",
            )
            audit("user_status_change", "User", target_user.id, detail)
            db.session.commit()
            flash("User status updated.", "success")
            return redirect(url_for("admin.users"))
    return render_template("admin/users.html", users=users, form=form, target_user=target_user)


@admin_bp.route("/categories", methods=["GET", "POST"])
@admin_required
def categories():
    form = CategoryForm()
    if form.validate_on_submit():
        category = Category(
            name=form.name.data.strip(),
            slug=form.slug.data.strip().lower(),
            description=form.description.data,
        )
        db.session.add(category)
        audit("create_category", "Category", detail=category.name)
        db.session.commit()
        flash("Category created.", "success")
        return redirect(url_for("admin.categories"))
    items = Category.query.order_by(Category.name).all()
    return render_template("admin/categories.html", categories=items, form=form)


@admin_bp.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_category(category_id: int):
    category = Category.query.get_or_404(category_id)
    form = CategoryForm(obj=category)
    if form.validate_on_submit():
        category.name = form.name.data.strip()
        category.slug = form.slug.data.strip().lower()
        category.description = form.description.data
        audit("edit_category", "Category", category.id, category.name)
        db.session.commit()
        flash("Category updated.", "success")
        return redirect(url_for("admin.categories"))
    return render_template("admin/category_form.html", form=form, category=category)


@admin_bp.route("/skills", methods=["GET", "POST"])
@admin_required
def skills():
    form = SkillForm()
    form.category_id.choices = [(category.id, category.name) for category in Category.query.order_by(Category.name).all()]
    if form.validate_on_submit():
        skill = Skill(
            name=form.name.data.strip(),
            description=form.description.data,
            category_id=form.category_id.data,
        )
        db.session.add(skill)
        audit("create_skill", "Skill", detail=skill.name)
        db.session.commit()
        flash("Skill created.", "success")
        return redirect(url_for("admin.skills"))
    items = Skill.query.order_by(Skill.name).all()
    return render_template("admin/skills.html", skills=items, form=form)
