from flask import Blueprint


exchanges_bp = Blueprint("exchanges", __name__, url_prefix="/exchanges")


from . import routes  # noqa: E402,F401
