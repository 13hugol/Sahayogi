from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..forms import CertificateForm, ProfileForm, ReportForm
from ..models import Certificate, Listing, Profile, Report, Review, Skill, User, utcnow
from ..services import save_upload, schedule_account_deletion, update_skill_links
from . import profile_bp


def _skill_choices():
    return [(skill.id, skill.name) for skill in Skill.query.order_by(Skill.name).all()]


@profile_bp.route("/me")
@login_required
def me():
    return redirect(url_for("profile.view", user_id=current_user.id))


@profile_bp.route("/users/<int:user_id>")
def view(user_id: int):
    user = User.query.get_or_404(user_id)
    if not user.profile:
        abort(404)
    approved_listings = user.listings.filter_by(status="approved").order_by(Listing.created_at.desc()).all()
    approved_certificates = user.certificates.filter_by(status="approved").all()
    recent_reviews = (
        Review.query.filter_by(reviewee_id=user.id)
        .order_by(Review.created_at.desc())
        .limit(10)
        .all()
    )
    report_form = ReportForm()
    return render_template(
        "profile/view.html",
        user=user,
        approved_listings=approved_listings,
        approved_certificates=approved_certificates,
        recent_reviews=recent_reviews,
        report_form=report_form,
    )


@profile_bp.route("/edit", methods=["GET", "POST"])
@login_required
def edit():
    form = ProfileForm(obj=current_user.profile)
    form.offered_skills.choices = _skill_choices()
    form.wanted_skills.choices = _skill_choices()
    if request.method == "GET":
        form.offered_skills.data = [entry.skill_id for entry in current_user.offered_skills]
        form.wanted_skills.data = [entry.skill_id for entry in current_user.wanted_skills]
    if form.validate_on_submit():
        existing = Profile.query.filter(
            Profile.username == form.username.data.strip(),
            Profile.user_id != current_user.id,
        ).first()
        if existing:
            form.username.errors.append("That username is already taken.")
            return render_template("profile/edit.html", form=form)
        profile = current_user.profile
        profile.username = form.username.data.strip()
        profile.headline = form.headline.data
        profile.bio = form.bio.data
        profile.location = form.location.data
        profile.city = form.city.data
        profile.country = form.country.data
        profile.contact_email = form.contact_email.data
        profile.latitude = form.latitude.data
        profile.longitude = form.longitude.data
        if form.avatar.data:
            profile.avatar_path = save_upload(form.avatar.data, "avatars", {"jpg", "jpeg", "png", "webp"})
        update_skill_links(current_user, form.offered_skills.data, form.wanted_skills.data)
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("profile.view", user_id=current_user.id))
    return render_template("profile/edit.html", form=form)


@profile_bp.route("/certificates", methods=["GET", "POST"])
@login_required
def certificates():
    form = CertificateForm()
    form.skill_id.choices = _skill_choices()
    if form.validate_on_submit():
        certificate = Certificate(
            user=current_user,
            skill_id=form.skill_id.data,
            file_path=save_upload(form.certificate.data, "certificates", {"pdf", "png", "jpg", "jpeg"}),
        )
        db.session.add(certificate)
        db.session.commit()
        flash("Certificate uploaded and queued for review.", "success")
        return redirect(url_for("profile.certificates"))
    items = current_user.certificates.order_by(Certificate.created_at.desc()).all()
    return render_template("profile/certificates.html", form=form, certificates=items)


@profile_bp.route("/users/<int:user_id>/report", methods=["POST"])
@login_required
def report(user_id: int):
    if user_id == current_user.id:
        abort(400)
    reported_user = User.query.get_or_404(user_id)
    form = ReportForm()
    if not form.validate_on_submit():
        flash("Please submit a valid report.", "danger")
        return redirect(url_for("profile.view", user_id=user_id))
    existing = (
        Report.query.filter_by(reporter_id=current_user.id, reported_user_id=user_id)
        .order_by(Report.created_at.desc())
        .first()
    )
    from datetime import timedelta

    if existing and existing.created_at >= utcnow() - timedelta(days=7):
        flash("You can only report the same user once every 7 days.", "warning")
        return redirect(url_for("profile.view", user_id=user_id))
    db.session.add(
        Report(
            reporter_id=current_user.id,
            reported_user_id=user_id,
            reason=form.reason.data,
            description=form.description.data,
        )
    )
    db.session.commit()
    flash("Report submitted.", "success")
    return redirect(url_for("profile.view", user_id=user_id))


@profile_bp.route("/delete", methods=["POST"])
@login_required
def delete_account():
    password = request.form.get("password", "")
    if not current_user.check_password(password):
        flash("Password confirmation failed.", "danger")
        return redirect(url_for("profile.edit"))
    schedule_account_deletion(current_user)
    db.session.commit()
    flash("Your account is now scheduled for deletion and can be purged after the grace period.", "warning")
    return redirect(url_for("auth.logout"))
