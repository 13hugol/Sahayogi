from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil

from flask import has_app_context

from app.models.category import Category
from app.repositories.category_repository import DEFAULT_CATEGORIES, CategoryRepository


LISTINGS_PER_PAGE = 20


@dataclass(frozen=True)
class Skill:
    id: int
    name: str


@dataclass(frozen=True)
class Availability:
    label: str


@dataclass(frozen=True)
class ListingProfile:
    location: str
    reputation_score: float
    contact_email: str | None = None
    review_count: int = 3


@dataclass(frozen=True)
class ListingUser:
    id: int
    full_name: str
    profile: ListingProfile
    verified_skill_ids: tuple[int, ...] = ()

    def has_verified_skill(self, skill_id: int) -> bool:
        return skill_id in self.verified_skill_ids


@dataclass(frozen=True)
class BrowseListing:
    id: int
    title: str
    description: str
    exchange_type: str
    min_credits: int
    location_text: str
    contact_method: str
    status: str
    created_at: datetime
    approved_at: datetime
    skill: Skill
    skill_id: int
    category: Category
    category_id: int
    user: ListingUser
    user_id: int
    availability: tuple[Availability, ...]


@dataclass(frozen=True)
class ListingPage:
    listings: list[BrowseListing]
    page: int
    total_pages: int
    total_results: int


@dataclass(frozen=True)
class CategoryOverviewItem:
    category: Category
    active_listing_count: int


def categories() -> list[Category]:
    if has_app_context():
        return CategoryRepository().active()
    return [
        Category(
            id=int(category["id"]),
            name=str(category["name"]),
            slug=str(category["slug"]),
            icon=str(category["icon"]),
            description=str(category["description"]),
            sort_order=int(category["sort_order"]),
        )
        for category in DEFAULT_CATEGORIES
    ]


def category_overview() -> list[CategoryOverviewItem]:
    counts = {}
    for listing in all_listings():
        if listing.status != "approved":
            continue
        counts[listing.category_id] = counts.get(listing.category_id, 0) + 1
    return [
        CategoryOverviewItem(category=category, active_listing_count=counts.get(category.id, 0))
        for category in categories()
    ]


def all_listings() -> list[BrowseListing]:
    return sorted(_build_catalog(), key=lambda listing: listing.approved_at, reverse=True)


def find_listing(listing_id: int) -> BrowseListing | None:
    return next((listing for listing in all_listings() if listing.id == listing_id), None)


def filter_listings(
    *,
    query: str = "",
    category_ids: set[int] | None = None,
    radius: str = "",
    listings: list[BrowseListing] | None = None,
) -> list[BrowseListing]:
    category_ids = category_ids or set()
    normalized_query = query.strip().lower()
    normalized_radius = radius.strip()
    source = listings if listings is not None else all_listings()
    filtered = []
    for listing in source:
        if category_ids and listing.category_id not in category_ids:
            continue
        if normalized_query and normalized_query not in _search_text(listing):
            continue
        if normalized_radius and not _within_radius(listing, normalized_radius):
            continue
        filtered.append(listing)
    return filtered


def paginate_listings(listings: list[BrowseListing], page: int, per_page: int = LISTINGS_PER_PAGE) -> ListingPage:
    total_results = len(listings)
    total_pages = max(ceil(total_results / per_page), 1)
    current_page = min(max(page, 1), total_pages)
    start = (current_page - 1) * per_page
    return ListingPage(
        listings=listings[start : start + per_page],
        page=current_page,
        total_pages=total_pages,
        total_results=total_results,
    )


def _search_text(listing: BrowseListing) -> str:
    values = (
        listing.title,
        listing.description,
        listing.skill.name,
        listing.category.name,
        listing.user.full_name,
        listing.location_text,
    )
    return " ".join(values).lower()


def _within_radius(listing: BrowseListing, radius: str) -> bool:
    remote_listing = "remote" in listing.location_text.lower()
    if radius == "100":
        return True
    if radius == "50":
        return remote_listing or any(place in listing.location_text.lower() for place in ("kathmandu", "lalitpur", "bhaktapur"))
    if radius == "10":
        return remote_listing or "kathmandu" in listing.location_text.lower()
    return True


def _build_catalog() -> list[BrowseListing]:
    category_by_id = {category.id: category for category in categories()}
    base_time = datetime(2026, 5, 28, 9, 0, 0)
    raw_listings = [
        (1, "Python Automation Basics", "Python scripting", "Build small scripts for files, spreadsheets, and repeatable admin work.", "credit", 12, "Kathmandu or remote", "Platform messaging", "Aarav Shrestha", 4.9, ("Weekday evenings", "Saturday morning")),
        (2, "Acoustic Guitar Fundamentals", "Guitar lessons", "Beginner-friendly rhythm, chord switching, and guitarist practice routines.", "teach", 0, "Lalitpur", "Platform messaging", "Maya Gurung", 4.8, ("Tuesday evening", "Friday afternoon")),
        (3, "Conversational Nepali Practice", "Nepali conversation", "Everyday Nepali speaking practice for learners who want confidence in local conversations.", "credit", 8, "Kathmandu", "In-app messaging", "Nima Lama", 4.7, ("Monday morning", "Thursday evening")),
        (4, "Newari Snack Workshop", "Newari cooking", "Hands-on bara, chatamari, and achar preparation with ingredient planning tips.", "credit", 14, "Bhaktapur", "Platform messaging", "Srijana Maharjan", 4.9, ("Sunday afternoon",)),
        (1, "Web Design With Flask", "Flask web design", "Jinja layouts, forms, simple routes, and practical debugging for student projects.", "credit", 16, "Remote", "Platform messaging", "Kiran Bista", 4.6, ("Wednesday evening", "Saturday afternoon")),
        (2, "Ukulele Starter Session", "Ukulele", "Strumming patterns, tuning habits, and three-song practice plan for new players.", "teach", 0, "Kathmandu or remote", "In-app messaging", "Riya Thapa", 4.5, ("Monday evening",)),
        (3, "English Interview Speaking", "English interview prep", "Practice concise answers, professional vocabulary, and follow-up questions.", "credit", 10, "Remote", "Platform messaging", "Suman Karki", 4.8, ("Weekday mornings",)),
        (4, "Budget Meal Prep", "Meal prep", "Plan affordable weekly meals with simple recipes, storage tips, and shopping lists.", "credit", 9, "Kathmandu", "Platform messaging", "Alisha Rai", 4.6, ("Saturday morning",)),
        (1, "Excel Dashboard Foundations", "Excel dashboards", "Turn raw tables into clean summaries with formulas, filters, and chart-ready ranges.", "teach", 0, "Lalitpur or remote", "Platform messaging", "Prabin Adhikari", 4.9, ("Tuesday morning", "Friday evening")),
        (2, "Basic Vocal Warmups", "Vocal training", "Breathing, pitch awareness, and safe warmup habits for everyday singing practice.", "credit", 7, "Kathmandu", "In-app messaging", "Anu Tamang", 4.4, ("Sunday morning",)),
        (3, "Japanese Hiragana Help", "Japanese basics", "Read and write hiragana with memory anchors and pronunciation checks.", "credit", 11, "Remote", "Platform messaging", "Bikash Pandey", 4.7, ("Thursday night",)),
        (4, "Cake Decorating Basics", "Cake decorating", "Buttercream handling, piping shapes, and simple celebration cake finishing.", "teach", 0, "Lalitpur", "Platform messaging", "Puja KC", 4.8, ("Friday afternoon",)),
        (1, "Canva For Student Reports", "Canva design", "Create clean reports, posters, and presentation visuals with reusable layouts.", "credit", 8, "Kathmandu or remote", "In-app messaging", "Ishan Joshi", 4.5, ("Wednesday afternoon",)),
        (2, "Madal Rhythm Practice", "Madal", "Core rhythm cycles, hand positioning, and folk-song accompaniment practice.", "credit", 13, "Bhaktapur", "Platform messaging", "Dawa Sherpa", 4.9, ("Saturday evening",)),
        (3, "Korean Reading Basics", "Korean hangul", "Hangul letters, pronunciation blocks, and simple reading drills.", "credit", 10, "Remote", "Platform messaging", "Sneha Basnet", 4.6, ("Monday night",)),
        (4, "Mo:Mo Folding Clinic", "MoMo making", "Dough handling, filling balance, and folding techniques for consistent mo:mo batches.", "credit", 12, "Kathmandu", "Platform messaging", "Kabita Shakya", 5.0, ("Sunday morning", "Sunday afternoon")),
        (1, "Git And GitHub Confidence", "GitHub workflow", "Practice commits, branches, pull requests, and resolving small merge conflicts.", "credit", 15, "Remote", "Platform messaging", "Rohit Khadka", 4.7, ("Tuesday evening",)),
        (2, "Keyboard Chords For Beginners", "Keyboard chords", "Major and minor chords, simple progressions, and practice rhythm.", "teach", 0, "Kathmandu", "In-app messaging", "Elina Maharjan", 4.6, ("Thursday evening",)),
        (3, "Hindi Conversation Exchange", "Hindi speaking", "Casual Hindi speaking practice with correction notes and vocabulary review.", "credit", 7, "Lalitpur or remote", "Platform messaging", "Amit Chaudhary", 4.4, ("Friday morning",)),
        (4, "Fermented Pickle Basics", "Pickle making", "Safe achar fermentation, spice balancing, and storage guidance.", "credit", 9, "Bhaktapur", "Platform messaging", "Mina Dangol", 4.7, ("Wednesday morning",)),
        (1, "Intro To Data Cleaning", "Data cleaning", "Clean CSV files, normalize columns, and prepare small datasets for analysis.", "credit", 14, "Remote", "Platform messaging", "Samir Poudel", 4.8, ("Saturday afternoon",)),
        (2, "Tabla Timing Drills", "Tabla", "Foundational bols, timing drills, and steady tempo practice.", "credit", 12, "Kathmandu", "Platform messaging", "Manish Shah", 4.9, ("Sunday evening",)),
        (3, "French Pronunciation Lab", "French pronunciation", "Practice vowels, liaison, and short cafe conversations.", "teach", 0, "Remote", "In-app messaging", "Leena Rana", 4.5, ("Tuesday night",)),
        (4, "Coffee Brewing At Home", "Coffee brewing", "Dial in grind, water ratio, and pour-over method without expensive equipment.", "credit", 8, "Kathmandu or remote", "Platform messaging", "Niraj Gurung", 4.6, ("Weekday mornings",)),
        (1, "Cyber Safety For Families", "Cyber safety", "Password habits, phishing checks, privacy settings, and safe device sharing.", "credit", 10, "Lalitpur", "Platform messaging", "Ashma Lama", 4.8, ("Thursday afternoon",)),
        (2, "Songwriting Feedback Circle", "Songwriting", "Shape lyrics, melody ideas, and song structure with practical peer feedback.", "credit", 9, "Remote", "In-app messaging", "Bibek Rai", 4.3, ("Friday night",)),
        (3, "Spanish Travel Phrases", "Spanish phrases", "Useful phrases for greetings, transit, food, and simple travel conversations.", "credit", 8, "Kathmandu or remote", "Platform messaging", "Sarita Bhandari", 4.6, ("Saturday morning",)),
        (4, "Sourdough Starter Care", "Sourdough", "Maintain a starter, read fermentation signs, and bake a simple loaf.", "teach", 0, "Remote", "Platform messaging", "Anmol Tamrakar", 4.7, ("Sunday afternoon",)),
        (1, "No-Code App Prototyping", "No-code prototyping", "Map a simple idea into screens, forms, and workflow logic using no-code tools.", "credit", 13, "Remote", "Platform messaging", "Deepa Ghimire", 4.6, ("Monday evening",)),
        (2, "Violin Posture Check", "Violin basics", "Bow hold, shoulder posture, and first-scale practice for beginner violinists.", "credit", 15, "Lalitpur", "Platform messaging", "Nabin Shrestha", 4.7, ("Wednesday evening",)),
        (3, "Academic Writing Polish", "Academic writing", "Improve thesis statements, paragraph flow, and citation-friendly wording.", "credit", 12, "Remote", "In-app messaging", "Kripa Acharya", 4.9, ("Weekday afternoons",)),
        (4, "Healthy Tiffin Ideas", "Tiffin planning", "Balanced lunchbox planning with fast prep, local ingredients, and variety.", "credit", 7, "Kathmandu", "Platform messaging", "Roshan Khatri", 4.4, ("Tuesday morning",)),
        (1, "Cloud Architecture Primer", "Cloud architecture", "Understand regions, services, budgets, and deployment choices for small apps.", "teach", 0, "Remote", "Platform messaging", "Sagar Neupane", 4.8, ("Thursday evening",)),
        (2, "Podcast Audio Cleanup", "Audio editing", "Clean spoken audio, reduce noise, and export publishable podcast clips.", "credit", 11, "Kathmandu or remote", "In-app messaging", "Asmita Regmi", 4.5, ("Friday afternoon",)),
        (3, "Public Speaking In English", "Public speaking", "Practice speeches, pacing, and confident delivery in English.", "credit", 10, "Lalitpur or remote", "Platform messaging", "Hemant Oli", 4.7, ("Monday afternoon",)),
        (4, "Candle Making For Gifts", "Candle making", "Wax safety, fragrance ratios, and simple gift-ready candle finishing.", "credit", 9, "Bhaktapur", "Platform messaging", "Rachana Tuladhar", 4.6, ("Saturday afternoon",)),
    ]

    listings = []
    for index, item in enumerate(raw_listings, start=1):
        category_id, title, skill_name, description, exchange_type, min_credits, location, contact, teacher, reputation, availability = item
        category = category_by_id[category_id]
        skill = Skill(index, skill_name)
        user_id = 100 + index
        user = ListingUser(
            id=user_id,
            full_name=teacher,
            profile=ListingProfile(location=location.replace(" or remote", ""), reputation_score=reputation, contact_email=None),
            verified_skill_ids=(skill.id,) if index % 3 == 1 else (),
        )
        approved_at = base_time - timedelta(hours=index - 1)
        listings.append(
            BrowseListing(
                id=index,
                title=title,
                description=description,
                exchange_type=exchange_type,
                min_credits=min_credits,
                location_text=location,
                contact_method=contact,
                status="approved",
                created_at=approved_at - timedelta(days=1),
                approved_at=approved_at,
                skill=skill,
                skill_id=skill.id,
                category=category,
                category_id=category.id,
                user=user,
                user_id=user.id,
                availability=tuple(Availability(label) for label in availability),
            )
        )
    return listings
