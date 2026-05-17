from __future__ import annotations

from flask import render_template
from flask_login import current_user, login_required

from ..extensions import db
from ..services import build_matches_for_user
from . import matches_bp


@matches_bp.route("/")
@login_required
def index():
    matches = build_matches_for_user(current_user)
    db.session.commit()
    return render_template("matches/index.html", matches=matches)
