from __future__ import annotations

import click
from flask import current_app

from .extensions import db
from .models import Category, Exchange, ExchangeCompletion, ExchangeRequest, Listing, ListingAvailability, Profile, Review, Role, Skill, User, UserSkillOffer, UserSkillWant, refresh_profile_metrics, utcnow
from .services import append_ledger_entry, purge_due_accounts, unique_username


REFERENCE_DATA = {
    "Programming": ["Python", "Flask", "SQL", "JavaScript"],
    "Creative": ["Graphic Design", "Photography", "Video Editing", "Writing"],
    "Business": ["Public Speaking", "Marketing", "Resume Review"],
    "Languages": ["English Conversation", "Nepali Basics", "Hindi Conversation"],
}


DEMO_USERS = [
    {
        "full_name": "Anisha Sharma",
        "email": "anisha@demo.local",
        "password": "Demo1234!",
        "location": "Kathmandu",
        "headline": "Python developer eager to learn design",
        "bio": "Full-stack developer with 3 years of experience. Looking to expand my creative skills.",
        "offered": ["Python", "Flask", "SQL"],
        "wanted": ["Graphic Design", "Photography"],
    },
    {
        "full_name": "Rajesh Tamang",
        "email": "rajesh@demo.local",
        "password": "Demo1234!",
        "location": "Pokhara",
        "headline": "Graphic designer who wants to learn coding",
        "bio": "Professional graphic designer with 5 years of experience. Ready to teach design in exchange for programming skills.",
        "offered": ["Graphic Design", "Photography"],
        "wanted": ["Python", "JavaScript"],
    },
    {
        "full_name": "Sunita Gurung",
        "email": "sunita@demo.local",
        "password": "Demo1234!",
        "location": "Lalitpur",
        "headline": "Marketing specialist open to skill exchange",
        "bio": "Marketing professional looking to learn new languages and teach business skills.",
        "offered": ["Marketing", "Public Speaking"],
        "wanted": ["English Conversation", "Video Editing"],
    },
    {
        "full_name": "Bikash Rai",
        "email": "bikash@demo.local",
        "password": "Demo1234!",
        "location": "Bhaktapur",
        "headline": "Language tutor and photography enthusiast",
        "bio": "Native Nepali speaker fluent in English. Happy to help with language skills.",
        "offered": ["English Conversation", "Nepali Basics"],
        "wanted": ["Photography", "Writing"],
    },
]


DEMO_LISTINGS = [
    {
        "user_email": "anisha@demo.local",
        "skill": "Python",
        "category": "Programming",
        "title": "Learn Python from scratch",
        "description": "I can teach Python fundamentals including data structures, OOP, and basic web scraping. Perfect for beginners.",
        "exchange_type": "teach",
        "location_text": "Kathmandu or remote",
        "contact_method": "Platform messaging",
        "availability": ["Weekday evenings", "Saturday remote"],
    },
    {
        "user_email": "rajesh@demo.local",
        "skill": "Graphic Design",
        "category": "Creative",
        "title": "Logo and brand identity design",
        "description": "Professional logo design and brand identity work. I'll teach you design thinking and Figma basics.",
        "exchange_type": "teach",
        "location_text": "Pokhara or remote",
        "contact_method": "Platform messaging",
        "availability": ["Weekends", "Remote"],
    },
    {
        "user_email": "sunita@demo.local",
        "skill": "Marketing",
        "category": "Business",
        "title": "Digital marketing fundamentals",
        "description": "Learn SEO basics, social media strategy, and content marketing from a practicing professional.",
        "exchange_type": "teach",
        "location_text": "Lalitpur",
        "contact_method": "Platform messaging",
        "availability": ["Tuesday evenings", "Thursday remote"],
    },
    {
        "user_email": "bikash@demo.local",
        "skill": "English Conversation",
        "category": "Languages",
        "title": "Conversational English practice",
        "description": "Practice speaking English in a relaxed environment. I'll help with pronunciation and fluency.",
        "exchange_type": "teach",
        "location_text": "Bhaktapur or remote",
        "contact_method": "Platform messaging",
        "availability": ["Morning sessions", "Remote"],
    },
]


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

    @app.cli.command("seed-demo-data")
    def seed_demo_data():
        """Seed the database with demo users, skills, listings, and exchanges."""
        db.create_all()
        seed_roles()
        seed_categories_and_skills()
        seed_demo_users()
        seed_demo_listings()
        seed_demo_exchanges()
        db.session.commit()
        click.echo("Demo data seeded successfully.")

    @app.cli.command("run-maintenance")
    def run_maintenance():
        purged = purge_due_accounts()
        for user in User.query.all():
            if user.profile:
                refresh_profile_metrics(user)
        db.session.commit()
        click.echo(f"Maintenance complete. Purged accounts: {purged}")

    @app.cli.command("elevate-user")
    @click.argument("email")
    def elevate_user(email):
        """Elevate a user to admin by their email address."""
        user = User.query.filter_by(email=email.lower().strip()).first()
        if not user:
            click.echo(f"Error: No user found with email '{email}'")
            return
            
        admin_role = Role.query.filter_by(name="admin").first()
        if not admin_role:
            click.echo("Error: Admin role does not exist in the database.")
            return
            
        user.role = admin_role
        db.session.commit()
        click.echo(f"Success: {user.full_name} ({user.email}) is now an admin!")


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


def seed_demo_users() -> None:
    user_role = Role.query.filter_by(name="user").first()
    if not user_role:
        user_role = Role(name="user", description="Platform member")
        db.session.add(user_role)
        db.session.flush()

    for demo in DEMO_USERS:
        if User.query.filter_by(email=demo["email"]).first():
            click.echo(f"  Skipping existing user: {demo['email']}")
            continue

        user = User(
            full_name=demo["full_name"],
            email=demo["email"],
            role=user_role,
            is_email_verified=True,
        )
        user.set_password(demo["password"])
        user.profile = Profile(
            username=unique_username(demo["full_name"].split()[0].lower()),
            location=demo["location"],
            headline=demo["headline"],
            bio=demo["bio"],
            contact_email=demo["email"],
        )
        db.session.add(user)
        db.session.flush()
        append_ledger_entry(user, current_app.config["INITIAL_CREDITS"], "welcome", "Welcome credit allocation.")

        for skill_name in demo["offered"]:
            skill = Skill.query.filter_by(name=skill_name).first()
            if skill:
                db.session.add(UserSkillOffer(user=user, skill_id=skill.id))

        for skill_name in demo["wanted"]:
            skill = Skill.query.filter_by(name=skill_name).first()
            if skill:
                db.session.add(UserSkillWant(user=user, skill_id=skill.id))

        click.echo(f"  Created demo user: {demo['full_name']} ({demo['email']})")


def seed_demo_listings() -> None:
    for listing_data in DEMO_LISTINGS:
        user = User.query.filter_by(email=listing_data["user_email"]).first()
        if not user:
            continue

        existing = Listing.query.filter_by(user_id=user.id, title=listing_data["title"]).first()
        if existing:
            click.echo(f"  Skipping existing listing: {listing_data['title']}")
            continue

        skill = Skill.query.filter_by(name=listing_data["skill"]).first()
        category = Category.query.filter_by(slug=listing_data["category"].lower().replace(" ", "-")).first()
        if not skill or not category:
            continue

        listing = Listing(
            user_id=user.id,
            skill_id=skill.id,
            category_id=category.id,
            title=listing_data["title"],
            description=listing_data["description"],
            exchange_type=listing_data["exchange_type"],
            location_text=listing_data["location_text"],
            contact_method=listing_data["contact_method"],
            status="approved",
        )
        listing.approved_at = utcnow()
        db.session.add(listing)
        db.session.flush()

        for label in listing_data["availability"]:
            is_remote = "remote" in label.lower()
            db.session.add(ListingAvailability(listing=listing, label=label, is_remote=is_remote))

        click.echo(f"  Created listing: {listing_data['title']}")


def seed_demo_exchanges() -> None:
    anisha = User.query.filter_by(email="anisha@demo.local").first()
    rajesh = User.query.filter_by(email="rajesh@demo.local").first()

    if not anisha or not rajesh:
        return

    python_skill = Skill.query.filter_by(name="Python").first()
    design_skill = Skill.query.filter_by(name="Graphic Design").first()
    python_listing = Listing.query.filter_by(user_id=anisha.id, skill_id=python_skill.id).first() if python_skill else None
    design_listing = Listing.query.filter_by(user_id=rajesh.id, skill_id=design_skill.id).first() if design_skill else None

    if not python_listing or not design_listing:
        return

    existing = Exchange.query.filter_by(teacher_id=anisha.id, learner_id=rajesh.id).first()
    if existing:
        click.echo("  Skipping existing demo exchange")
        return

    request = ExchangeRequest(
        listing_id=python_listing.id,
        sender_id=rajesh.id,
        recipient_id=anisha.id,
        request_type="barter",
        offered_skill_id=design_skill.id,
        requested_message="I'd love to learn Python in exchange for teaching you design!",
        status="accepted",
    )
    db.session.add(request)
    db.session.flush()

    exchange = Exchange(
        request_id=request.id,
        listing_id=python_listing.id,
        teacher_id=anisha.id,
        learner_id=rajesh.id,
        barter_skill_id=design_skill.id,
        exchange_type="teach",
        status="completed",
    )
    exchange.completed_at = utcnow()
    db.session.add(exchange)
    db.session.flush()

    db.session.add(ExchangeCompletion(exchange=exchange, user=anisha))
    db.session.add(ExchangeCompletion(exchange=exchange, user=rajesh))

    review1 = Review(exchange=exchange, reviewer_id=rajesh.id, reviewee_id=anisha.id, rating=5, comment="Anisha is a fantastic Python teacher!")
    review2 = Review(exchange=exchange, reviewer_id=anisha.id, reviewee_id=rajesh.id, rating=5, comment="Great design lessons, very patient teacher.")
    db.session.add(review1)
    db.session.add(review2)

    refresh_profile_metrics(anisha)
    refresh_profile_metrics(rajesh)

    click.echo("  Created demo exchange with reviews")
