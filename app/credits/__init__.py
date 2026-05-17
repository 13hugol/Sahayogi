from flask import Blueprint


credits_bp = Blueprint("credits", __name__, url_prefix="/credits")


from . import routes  # noqa: E402,F401
