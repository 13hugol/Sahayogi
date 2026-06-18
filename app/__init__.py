from __future__ import annotations

import os
from datetime import timedelta

from flask import Flask, abort, render_template, request, session, redirect, url_for, flash
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
    app.permanent_session_lifetime = timedelta(days=7)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    with app.app_context():
        Database.create_tables()

    register_csrf(app)
    register_status_check(app)
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


def register_status_check(app: Flask) -> None:
    @app.before_request
    def check_user_status():
        from flask_login import current_user, logout_user
        from app.models.user import User
        from app.repositories import UserRepository
        from datetime import datetime
        
        if request.endpoint == 'static' or request.endpoint == 'auth.logout':
            return None
            
        if current_user and current_user.is_authenticated:
            user = User.find_by_id(current_user.id)
            if user:
                from app.database import Database
                db = Database()
                try:
                    db.execute("UPDATE users SET last_active_at = %s WHERE id = %s", (datetime.utcnow(), user.id))
                finally:
                    db.close()
                current_user.status = user.status
                current_user.suspended_until = user.suspended_until
                current_user.suspension_reason = user.suspension_reason
                
                if user.status == "suspended":
                    if user.suspended_until and user.suspended_until <= datetime.utcnow():
                        user.status = "active"
                        user.suspended_until = None
                        user.suspension_reason = None
                        UserRepository().update_status(user.id, "active", None, None)
                        current_user.status = "active"
                    else:
                        logout_user()
                        session.pop("csrf_token", None)
                        local_time_str = user.suspended_until.strftime('%Y-%m-%d %H:%M:%S')
                        flash(f"Your account has been suspended until {local_time_str} UTC. Reason: {user.suspension_reason}", "danger")
                        return redirect(url_for("auth.login"))
                elif user.status == "banned":
                    logout_user()
                    session.pop("csrf_token", None)
                    flash(f"Your account has been permanently banned. Reason: {user.suspension_reason}", "danger")
                    return redirect(url_for("auth.login"))
        return None


def register_template_context(app: Flask) -> None:
    @app.context_processor
    def inject_template_state():
        from flask_login import current_user
        from app.models.notification import Notification

        unread_notifications = 0
        available_credits = 0
        if current_user and current_user.is_authenticated:
            try:
                unread_notifications = Notification.get_unread_count(current_user.id)
                available_credits = current_user.available_credit_balance
            except Exception:
                pass

        return {
            "available_credits": available_credits,
            "nav_counts": {"messages": 0, "notifications": unread_notifications},
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
