from __future__ import annotations

import click
from flask import current_app

from .extensions import db
from .models import Category, Role, Skill, User, refresh_profile_metrics
from .services import append_ledger_entry, purge_due_accounts, unique_username


REFERENCE_DATA = {
    "Programming": ["Python", "Flask", "SQL", "JavaScript"],
    "Creative": ["Graphic Design", "Photography", "Video Editing", "Writing"],
    "Business": ["Public Speaking", "Marketing", "Resume Review"],
    "Languages": ["English Conversation", "Nepali Basics", "Hindi Conversation"],
}


def register_commands(app):
    @app.cli.command("init-db")
    def init_db():
        db.create_all()
        click.echo("Database tables created.")

    @app.cli.command("seed-reference-data")
    def seed_reference_data():
        db.create_all()
        seed_roles()
        seed_categories_and_skills()
        seed_admin()
        db.session.commit()
        click.echo("Reference data seeded.")

    @app.cli.command("run-maintenance")
    def run_maintenance():
        purged = purge_due_accounts()
        for user in User.query.all():
            if user.profile:
                refresh_profile_metrics(user)
        db.session.commit()
        click.echo(f"Maintenance complete. Purged accounts: {purged}")


def seed_roles() -> None:
    for name, description in [("admin", "Administrator"), ("user", "Platform member")]:
        if not Role.query.filter_by(name=name).first():
            db.session.add(Role(name=name, description=description))
    db.session.flush()


def seed_categories_and_skills() -> None:
    for category_name, skill_names in REFERENCE_DATA.items():
        slug = category_name.lower().replace(" ", "-")
        category = Category.query.filter_by(slug=slug).first()
        if not category:
            category = Category(name=category_name, slug=slug, description=f"{category_name} skills.")
            db.session.add(category)
            db.session.flush()
        for skill_name in skill_names:
            if not Skill.query.filter_by(name=skill_name).first():
                db.session.add(Skill(name=skill_name, category=category, description=f"{skill_name} expertise."))


def seed_admin() -> None:
    admin_role = Role.query.filter_by(name="admin").first()
    email = current_app.config["DEFAULT_ADMIN_EMAIL"]
    if User.query.filter_by(email=email).first():
        return
    admin = User(
        full_name=current_app.config["DEFAULT_ADMIN_NAME"],
        email=email,
        role=admin_role,
        is_email_verified=True,
    )
    admin.set_password(current_app.config["DEFAULT_ADMIN_PASSWORD"])
    from .models import Profile

    admin.profile = Profile(username=unique_username("admin"), contact_email=email, bio="Platform administrator.")
    db.session.add(admin)
    db.session.flush()
    append_ledger_entry(admin, 0, "system", "Administrator account created.")
