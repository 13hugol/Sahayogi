from __future__ import annotations

import click
from flask import current_app

from .database import Database
from .models import Role, User
from .models.admin_audit import AdminAuditLog
from .models.user import Profile
from .utils.email import send_email


def register_commands(app):
    @app.cli.command("init-db")
    def init_db():
        Database.create_tables()
        click.echo("Database tables created.")

    @app.cli.command("seed-reference-data")
    def seed_reference_data_command():
        seed_roles()
        seed_admin()
        seed_categories()
        click.echo("Reference data seeded: roles and admin account.")

    @app.cli.command("seed-demo-data")
    def seed_demo_data():
        click.echo("Skipped: demo data is outside the current backend scope.")

    @app.cli.command("run-maintenance")
    def run_maintenance():
        click.echo("No maintenance tasks are active in the current backend scope.")

    @app.cli.command("elevate-user")
    @click.argument("email")
    def elevate_user(email):
        user = User.find_by_email(email)
        if not user:
            click.echo(f"Error: no user found with email '{email}'.")
            return
        admin_role = Role.ensure("admin", "Administrator")
        user.update_role(admin_role)
        click.echo(f"Success: {user.full_name} ({user.email}) is now an admin.")

    @app.cli.command("test-email")
    @click.argument("recipient")
    def test_email(recipient):
        sent = send_email(
            "Sahayogi email test",
            recipient,
            "This is a test email from your Sahayogi configuration.",
        )
        if sent:
            click.echo(f"Email sent to {recipient}.")
        else:
            click.echo(f"Email was captured in {current_app.config['MAIL_LOG_FILE']}.")


def seed_roles() -> None:
    Role.ensure("admin", "Administrator")
    Role.ensure("user", "Platform member")


def seed_admin() -> None:
    admin_role = Role.ensure("admin", "Administrator")
    email = current_app.config["DEFAULT_ADMIN_EMAIL"].lower().strip()
    if User.find_by_email(email):
        return
    admin = User.create_registered(
        current_app.config["DEFAULT_ADMIN_NAME"],
        email,
        current_app.config["DEFAULT_ADMIN_PASSWORD"],
        "Kathmandu",
        admin_role,
    )
    admin.mark_email_verified()
    AdminAuditLog.create(
        admin_id=admin.id,
        action="seed_admin",
        target_type="User",
        target_id=admin.id,
        detail="Default administrator account created.",
    )


def seed_categories() -> None:
    categories = [
        ("Tech", "Technical skills and programming"),
        ("Music", "Instrument learning and music theory"),
        ("Language", "Foreign languages and linguistics"),
        ("Kitchen", "Cooking, baking, and culinary arts"),
    ]
    db = Database()
    try:
        for name, desc in categories:
            row = db.fetch_one("SELECT id FROM categories WHERE name = %s", (name,))
            if not row:
                db.execute("INSERT INTO categories (name, description) VALUES (%s, %s)", (name, desc))
    finally:
        db.close()

