from __future__ import annotations

import hashlib

from flask import current_app, has_app_context
from werkzeug.security import check_password_hash, generate_password_hash

DEFAULT_PASSWORD_HASH_METHOD = "scrypt"


def password_hash_method() -> str:
    if has_app_context():
        return current_app.config.get("PASSWORD_HASH_METHOD", DEFAULT_PASSWORD_HASH_METHOD)
    return DEFAULT_PASSWORD_HASH_METHOD


def hash_password(password: str) -> str:
    return generate_password_hash(password, method=password_hash_method())


def verify_password(password_hash: str, password: str) -> bool:
    return check_password_hash(password_hash, password)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
