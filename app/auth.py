from __future__ import annotations

from functools import wraps

from flask import abort, redirect, url_for
from flask_login import current_user, login_required


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


__all__ = ["admin_required", "login_required"]
