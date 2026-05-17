from __future__ import annotations

from flask import abort, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..forms import MessageForm
from ..models import Conversation, Message
from ..services import can_access_conversation, create_notification, mark_conversation_read, unread_counts_for
from . import messages_bp


def _user_conversations():
    conversations = Conversation.query.filter(
        (Conversation.user_one_id == current_user.id) | (Conversation.user_two_id == current_user.id)
    ).all()
    return sorted(
        conversations,
        key=lambda conversation: (
            conversation.messages.order_by(Message.created_at.desc()).first().created_at
            if conversation.messages.count()
            else conversation.created_at
        ),
        reverse=True,
    )


@messages_bp.route("/")
@login_required
def index():
    conversations = _user_conversations()
    return render_template("messages/index.html", conversations=conversations)


@messages_bp.route("/<int:conversation_id>", methods=["GET", "POST"])
@login_required
def detail(conversation_id: int):
    conversation = Conversation.query.get_or_404(conversation_id)
    if not can_access_conversation(conversation, current_user.id):
        abort(403)
    form = MessageForm()
    if form.validate_on_submit():
        message = Message(conversation=conversation, sender=current_user, body=form.body.data.strip())
        db.session.add(message)
        other_user = conversation.other_participant(current_user.id)
        if other_user:
            create_notification(
                other_user,
                "New message",
                f"You received a new message about '{conversation.subject}'.",
                url_for("messages.detail", conversation_id=conversation.id),
                "info",
            )
        db.session.commit()
        if request.is_json:
            return jsonify({"ok": True, "message": serialize_message(message), "counts": unread_counts_for(current_user)})
        return redirect(url_for("messages.detail", conversation_id=conversation.id))
    mark_conversation_read(conversation, current_user)
    db.session.commit()
    ordered_messages = conversation.messages.order_by(Message.created_at.asc()).all()
    return render_template(
        "messages/detail.html",
        conversation=conversation,
        form=form,
        conversations=_user_conversations(),
        ordered_messages=ordered_messages,
    )


@messages_bp.route("/<int:conversation_id>/messages.json")
@login_required
def messages_json(conversation_id: int):
    conversation = Conversation.query.get_or_404(conversation_id)
    if not can_access_conversation(conversation, current_user.id):
        abort(403)
    mark_conversation_read(conversation, current_user)
    db.session.commit()
    return jsonify(
        {
            "messages": [serialize_message(message) for message in conversation.messages.order_by(Message.created_at.asc()).all()],
            "counts": unread_counts_for(current_user),
        }
    )


@messages_bp.route("/<int:conversation_id>/send.json", methods=["POST"])
@login_required
def send_json(conversation_id: int):
    conversation = Conversation.query.get_or_404(conversation_id)
    if not can_access_conversation(conversation, current_user.id):
        abort(403)
    payload = request.get_json(silent=True) or {}
    body = (payload.get("body") or "").strip()
    if not body:
        return jsonify({"ok": False, "error": "Message body is required."}), 400
    message = Message(conversation=conversation, sender=current_user, body=body)
    db.session.add(message)
    other_user = conversation.other_participant(current_user.id)
    if other_user:
        create_notification(
            other_user,
            "New message",
            f"You received a new message about '{conversation.subject}'.",
            url_for("messages.detail", conversation_id=conversation.id),
            "info",
        )
    db.session.commit()
    return jsonify({"ok": True, "message": serialize_message(message), "counts": unread_counts_for(current_user)})


def serialize_message(message: Message) -> dict:
    return {
        "id": message.id,
        "sender": message.sender.full_name,
        "sender_id": message.sender_id,
        "body": message.body,
        "created_at": message.created_at.isoformat(),
    }
