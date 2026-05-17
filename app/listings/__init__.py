from flask import Blueprint


listings_bp = Blueprint("listings", __name__, url_prefix="/listings")


from . import routes  # noqa: E402,F401
