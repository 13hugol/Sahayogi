from __future__ import annotations

from app.models.category import Category

from .base_repository import BaseRepository


DEFAULT_CATEGORIES: tuple[dict[str, object], ...] = (
    {
        "id": 1,
        "name": "Tech",
        "slug": "tech",
        "icon": "TECH",
        "description": "Programming, digital tools, computing, and productivity skills.",
        "sort_order": 1,
    },
    {
        "id": 2,
        "name": "Music",
        "slug": "music",
        "icon": "MUS",
        "description": "Instrument, rhythm, vocal, audio, and creative practice sessions.",
        "sort_order": 2,
    },
    {
        "id": 3,
        "name": "Language",
        "slug": "language",
        "icon": "LANG",
        "description": "Conversation, reading, writing, pronunciation, and interview practice.",
        "sort_order": 3,
    },
    {
        "id": 4,
        "name": "Kitchen",
        "slug": "kitchen",
        "icon": "KIT",
        "description": "Cooking, baking, food planning, and practical home skills.",
        "sort_order": 4,
    },
)


class CategoryRepository(BaseRepository):
    def seed_defaults(self) -> None:
        with self._db() as db:
            db.execute_many(
                """
                INSERT IGNORE INTO categories
                    (id, name, slug, icon, description, sort_order)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    (
                        category["id"],
                        category["name"],
                        category["slug"],
                        category["icon"],
                        category["description"],
                        category["sort_order"],
                    )
                    for category in DEFAULT_CATEGORIES
                ),
            )

    def all(self) -> list[Category]:
        with self._db() as db:
            rows = db.fetch_all(
                """
                SELECT *
                FROM categories
                ORDER BY sort_order ASC, name ASC
                """
            )
        return [category for row in rows if (category := Category.from_row(row))]

    def active(self) -> list[Category]:
        with self._db() as db:
            rows = db.fetch_all(
                """
                SELECT *
                FROM categories
                WHERE is_active = TRUE
                ORDER BY sort_order ASC, name ASC
                """
            )
        return [category for row in rows if (category := Category.from_row(row))]

    def find_by_id(self, category_id: int) -> Category | None:
        with self._db() as db:
            row = db.fetch_one("SELECT * FROM categories WHERE id = %s", (category_id,))
        return Category.from_row(row)

    def name_exists(self, name: str, *, exclude_id: int | None = None) -> bool:
        params: tuple[object, ...]
        query = "SELECT id FROM categories WHERE LOWER(name) = LOWER(%s)"
        params = (name,)
        if exclude_id is not None:
            query += " AND id <> %s"
            params = (name, exclude_id)
        with self._db() as db:
            row = db.fetch_one(query, params)
        return row is not None

    def slug_exists(self, slug: str, *, exclude_id: int | None = None) -> bool:
        params: tuple[object, ...]
        query = "SELECT id FROM categories WHERE slug = %s"
        params = (slug,)
        if exclude_id is not None:
            query += " AND id <> %s"
            params = (slug, exclude_id)
        with self._db() as db:
            row = db.fetch_one(query, params)
        return row is not None

    def create(self, *, name: str, slug: str, icon: str, description: str) -> Category:
        with self._db() as db:
            sort_row = db.fetch_one("SELECT COALESCE(MAX(sort_order), 0) + 1 AS next_order FROM categories")
            category_id = db.execute(
                """
                INSERT INTO categories (name, slug, icon, description, sort_order)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (name, slug, icon, description, int((sort_row or {}).get("next_order") or 1)),
            )
            row = db.fetch_one("SELECT * FROM categories WHERE id = %s", (category_id,))
        return Category.from_row(row)

    def update(self, category_id: int, *, name: str, slug: str, icon: str, description: str) -> Category | None:
        with self._db() as db:
            db.execute(
                """
                UPDATE categories
                SET name = %s, slug = %s, icon = %s, description = %s
                WHERE id = %s
                """,
                (name, slug, icon, description, category_id),
            )
            row = db.fetch_one("SELECT * FROM categories WHERE id = %s", (category_id,))
        return Category.from_row(row)

