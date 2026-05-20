from __future__ import annotations

from flask import current_app
from itsdangerous import URLSafeTimedSerializer


def serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def generate_token(email: str, purpose: str) -> str:
    return serializer().dumps({"email": email, "purpose": purpose})


def validate_token(token: str, purpose: str, max_age: int) -> str | None:
    try:
        payload = serializer().loads(token, max_age=max_age)
    except Exception:
        return None
    if payload.get("purpose") != purpose:
        return None
    return payload.get("email")
