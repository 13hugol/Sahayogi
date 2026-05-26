from __future__ import annotations

import math

from app.repositories import SkillSearchRepository


class SkillSearchService:
    def __init__(self, search_repository: SkillSearchRepository):
        self._search_repository = search_repository

    def search(self, keyword: str = "", *, page: int = 1, per_page: int = 20):
        page = max(page, 1)
        per_page = max(1, min(per_page, 20))
        keyword = " ".join((keyword or "").split())
        listings, total_results = self._search_repository.search(
            keyword,
            limit=per_page,
            offset=(page - 1) * per_page,
        )
        total_pages = max(1, math.ceil(total_results / per_page))
        return {
            "listings": listings,
            "total_results": total_results,
            "total_pages": total_pages,
            "page": page,
            "keyword": keyword,
        }

    def find_listing(self, listing_id: int):
        return self._search_repository.find_by_id(listing_id)
