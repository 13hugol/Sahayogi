from flask import Blueprint


matches_bp = Blueprint("matches", __name__, url_prefix="/matches")


from . import routes  # noqa: E402,F401
