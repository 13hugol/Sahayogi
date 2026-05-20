from __future__ import annotations

import os

from flask import Flask, abort, render_template, request, session
from flask_login import LoginManager

from config import Config

from .commands import register_commands
from .database import Database
from .models import User

login_manager = LoginManager()


def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)
    config_object.validate()
    app.secret_key = app.config["SECRET_KEY"]

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    with app.app_context():
        Database.create_tables()

    register_csrf(app)
    register_blueprints(app)
    register_commands(app)
    register_template_context(app)
    register_error_handlers(app)

    return app


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    if not user_id.isdigit():
        return None
    return User.find_by_id(int(user_id))


def register_blueprints(app: Flask) -> None:
    from .routes.admin_routes import AdminRoutes
    from .routes.auth_routes import AuthRoutes
    from .routes.frontend_routes import FrontendRoutes
    from .routes.main_routes import MainRoutes

    app.register_blueprint(MainRoutes().register())
    app.register_blueprint(AuthRoutes().register())
    app.register_blueprint(AdminRoutes().register())
    for blueprint in FrontendRoutes().register():
        app.register_blueprint(blueprint)


def register_csrf(app: Flask) -> None:
    @app.before_request
    def csrf_protect():
        if "csrf_token" not in session:
            session["csrf_token"] = os.urandom(16).hex()
        if not app.config.get("WTF_CSRF_ENABLED", True):
            return None
        if request.method == "POST":
            token = request.form.get("csrf_token")
            if not token or token != session.get("csrf_token"):
                abort(403)
        return None


def register_template_context(app: Flask) -> None:
    @app.context_processor
    def inject_template_state():
        return {
            "available_credits": 0,
            "nav_counts": {"messages": 0, "notifications": 0},
            "csrf_token": lambda: session.get("csrf_token", ""),
        }


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(_error):
        return render_template("errors/500.html"), 500
