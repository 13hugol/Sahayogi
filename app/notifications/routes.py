from __future__ import annotations

from flask import abort, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Notification
from ..services import unread_counts_for
from . import notifications_bp


@notifications_bp.route("/")
@login_required
def index():
    notifications = current_user.notifications.order_by(Notification.created_at.desc()).all()
    return render_template("notifications/index.html", notifications=notifications)


@notifications_bp.route("/feed")
@login_required
def feed():
    items = current_user.notifications.order_by(Notification.created_at.desc()).limit(10).all()
    return jsonify(
        {
            "items": [
                {
                    "id": item.id,
                    "title": item.title,
                    "body": item.body,
                    "url": item.url,
                    "is_read": item.is_read,
                    "created_at": item.created_at.isoformat(),
                }
                for item in items
            ]
        }
    )


@notifications_bp.route("/counts")
@login_required
def counts():
    return jsonify(unread_counts_for(current_user))


@notifications_bp.route("/mark-all-read", methods=["POST"])
@login_required
def mark_all_read():
    for item in current_user.notifications.filter_by(is_read=False).all():
        item.is_read = True
        item.read_at = item.created_at
    db.session.commit()
    if request.is_json:
        return jsonify({"ok": True, "counts": unread_counts_for(current_user)})
    return redirect(url_for("notifications.index"))


@notifications_bp.route("/<int:notification_id>/open")
@login_required
def open_item(notification_id: int):
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id != current_user.id:
        abort(403)
    notification.is_read = True
    notification.read_at = notification.created_at
    db.session.commit()
    return redirect(notification.url or url_for("notifications.index"))
