from __future__ import annotations

from app.models import SkillSearchListing

from .base_repository import BaseRepository


class SkillSearchRepository(BaseRepository):
    def search(self, keyword: str = "", *, limit: int = 20, offset: int = 0) -> tuple[list[SkillSearchListing], int]:
        keyword = keyword.strip()
        params: list[object] = []
        where = "WHERE status = 'approved'"
        if keyword:
            pattern = f"%{keyword}%"
            where += " AND (title LIKE %s OR description LIKE %s)"
            params.extend([pattern, pattern])

        with self._db() as db:
            count_row = db.fetch_one(
                f"SELECT COUNT(*) AS count FROM skill_search_listings {where}",
                tuple(params),
            )
            rows = db.fetch_all(
                f"""
                SELECT *
                FROM skill_search_listings
                {where}
                ORDER BY created_at DESC, id DESC
                LIMIT %s OFFSET %s
                """,
                (*params, limit, offset),
            )
        listings = [listing for row in rows if (listing := SkillSearchListing.from_row(row))]
        return listings, int((count_row or {}).get("count") or 0)

    def find_by_id(self, listing_id: int) -> SkillSearchListing | None:
        with self._db() as db:
            row = db.fetch_one(
                """
                SELECT *
                FROM skill_search_listings
                WHERE id = %s AND status = 'approved'
                """,
                (listing_id,),
            )
        return SkillSearchListing.from_row(row)
