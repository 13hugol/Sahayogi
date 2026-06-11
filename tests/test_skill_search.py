from __future__ import annotations

from app.repositories import SkillSearchRepository
from app.services import SkillSearchService


SEARCH_ROWS = [
    {
        "id": 1,
        "title": "Guitar lessons for beginners",
        "skill_name": "Guitar",
        "category_id": 2,
        "category_name": "Music",
        "provider_name": "Aarav Shrestha",
        "provider_location": "Kathmandu",
        "description": "Friendly acoustic lessons covering chords and rhythm.",
        "exchange_type": "credit",
        "min_credits": 10,
        "location_text": "Kathmandu or remote",
        "contact_method": "In-app messaging",
        "reputation_score": 4.7,
        "status": "approved",
    },
    {
        "id": 2,
        "title": "Guitarist jam and stage confidence",
        "skill_name": "Guitar performance",
        "category_id": 2,
        "category_name": "Music",
        "provider_name": "Mina Rai",
        "provider_location": "Lalitpur",
        "description": "Practice timing, improvisation, and performance confidence.",
        "exchange_type": "teach",
        "min_credits": 0,
        "location_text": "Lalitpur",
        "contact_method": "In-app messaging",
        "reputation_score": 4.9,
        "status": "approved",
    },
    {
        "id": 3,
        "title": "Python web basics",
        "skill_name": "Python",
        "category_id": 1,
        "category_name": "Tech",
        "provider_name": "Sanjay Thapa",
        "provider_location": "Bhaktapur",
        "description": "Learn Flask routes, templates, and database-backed pages.",
        "exchange_type": "credit",
        "min_credits": 12,
        "location_text": "Remote",
        "contact_method": "In-app messaging",
        "reputation_score": 4.5,
        "status": "approved",
    },
]


def test_search_skills_matches_title_with_partial_keywords():
    service = SkillSearchService(SkillSearchRepository(db_factory=lambda: FakeSearchDb(SEARCH_ROWS)))

    results = service.search("guitar")

    assert results["total_results"] == 2
    titles = [listing.title for listing in results["listings"]]
    assert "Guitar lessons for beginners" in titles
    assert "Guitarist jam and stage confidence" in titles


def test_search_skills_matches_description_keywords():
    service = SkillSearchService(SkillSearchRepository(db_factory=lambda: FakeSearchDb(SEARCH_ROWS)))

    results = service.search("Flask")

    assert results["total_results"] == 1
    assert results["listings"][0].title == "Python web basics"


def test_search_skills_returns_friendly_empty_state_data():
    service = SkillSearchService(SkillSearchRepository(db_factory=lambda: FakeSearchDb(SEARCH_ROWS)))

    results = service.search("watercolor")

    assert results["total_results"] == 0
    assert results["listings"] == []
    assert results["total_pages"] == 1


class FakeSearchDb:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def fetch_one(self, query, params=None):
        if "COUNT" in query:
            return {"count": len(self._matching_rows(params))}
        listing_id = (params or [None])[0]
        return next((row for row in self.rows if row["id"] == listing_id and row["status"] == "approved"), None)

    def fetch_all(self, _query, params=None):
        rows = self._matching_rows(params)
        limit = params[-2] if params else 20
        offset = params[-1] if params else 0
        return rows[offset : offset + limit]

    def _matching_rows(self, params):
        approved_rows = [row for row in self.rows if row["status"] == "approved"]
        if not params or len(params) < 2:
            return approved_rows
        keyword = str(params[0]).strip("%").lower()
        return [
            row
            for row in approved_rows
            if keyword in row["title"].lower() or keyword in row["description"].lower()
        ]
