from __future__ import annotations

import os

from dotenv import load_dotenv
from flask import Flask, flash, redirect, url_for
from flask_login import current_user

from config import Config

from .commands import register_commands
from .extensions import bcrypt, db, login_manager, migrate
from .models import Role, unread_message_count
from .services import normalize_account_status, unread_counts_for


def create_app(config_object: type[Config] = Config) -> Flask:
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    register_blueprints(app)
    register_commands(app)
    register_context(app)
    register_hooks(app)

    return app


def register_blueprints(app: Flask) -> None:
    from .admin import admin_bp
    from .auth import auth_bp
    from .credits import credits_bp
    from .exchanges import exchanges_bp
    from .listings import listings_bp
    from .main import main_bp
    from .matches import matches_bp
    from .messages import messages_bp
    from .notifications import notifications_bp
    from .profile import profile_bp
    from .requests_bp import requests_bp
    from .reviews import reviews_bp

    for blueprint in [
        main_bp,
        auth_bp,
        profile_bp,
        listings_bp,
        matches_bp,
        requests_bp,
        exchanges_bp,
        messages_bp,
        notifications_bp,
        reviews_bp,
        credits_bp,
        admin_bp,
    ]:
        app.register_blueprint(blueprint)


def register_context(app: Flask) -> None:
    @app.context_processor
    def inject_navigation_state():
        counts = {"notifications": 0, "messages": 0}
        available_credits = None
        if current_user.is_authenticated:
            counts = unread_counts_for(current_user)
            available_credits = current_user.available_credit_balance
        return {
            "nav_counts": counts,
            "available_credits": available_credits,
        }


def register_hooks(app: Flask) -> None:
    @app.before_request
    def protect_account_state():
        if current_user.is_authenticated:
            normalize_account_status(current_user)
            if current_user.deleted_at:
                flash("Your account is scheduled for deletion and cannot be used right now.", "warning")
                return redirect(url_for("auth.logout"))
            if current_user.status == "banned":
                flash("Your account has been banned.", "danger")
                return redirect(url_for("auth.logout"))
            if current_user.status == "suspended" and not current_user.is_active:
                flash("Your account is suspended.", "warning")
                return redirect(url_for("auth.logout"))

    @app.shell_context_processor
    def shell_context():
        return {
            "db": db,
            "Role": Role,
            "unread_message_count": unread_message_count,
        }
