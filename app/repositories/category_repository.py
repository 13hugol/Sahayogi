from __future__ import annotations

from app.models.category import Category

from .base_repository import BaseRepository


def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "category"


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

    def find_by_name(self, name: str) -> Category | None:
        with self._db() as db:
            row = db.fetch_one("SELECT * FROM categories WHERE LOWER(name) = LOWER(%s)", (name.strip(),))
        return Category.from_row(row)

    def find_by_slug(self, slug: str) -> Category | None:
        with self._db() as db:
            row = db.fetch_one("SELECT * FROM categories WHERE slug = %s", (slug.strip(),))
        return Category.from_row(row)

    def all_with_counts(self) -> list[dict]:
        with self._db() as db:
            rows = db.fetch_all(
                """
                SELECT c.*, COUNT(s.id) AS listing_count
                FROM categories c
                LEFT JOIN skills s ON s.category_id = c.id AND s.status = 'approved'
                WHERE c.is_active = TRUE
                GROUP BY c.id
                ORDER BY c.sort_order ASC, c.name ASC
                """
            )
        return rows or []

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

    def ensure(
        self,
        name: str,
        description: str | None = None,
        icon: str = "CAT",
        sort_order: int = 0,
    ) -> Category:
        existing = self.find_by_name(name)
        if existing:
            return existing
        return self.create(name=name, description=description, icon=icon, sort_order=sort_order)

    def create(
        self,
        *,
        name: str,
        slug: str | None = None,
        icon: str = "CAT",
        description: str | None = "",
        sort_order: int | None = None,
        is_active: bool = True,
    ) -> Category:
        with self._db() as db:
            if sort_order is None:
                sort_row = db.fetch_one("SELECT COALESCE(MAX(sort_order), 0) + 1 AS next_order FROM categories")
                sort_order = int((sort_row or {}).get("next_order") or 1)
            category_id = db.execute(
                """
                INSERT INTO categories (name, slug, icon, description, sort_order, is_active)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (name.strip(), slug or _slugify(name), (icon or "CAT")[:16], description, int(sort_order), bool(is_active)),
            )
            row = db.fetch_one("SELECT * FROM categories WHERE id = %s", (category_id,))
        return Category.from_row(row)

    def update(
        self,
        category_id: int,
        *,
        name: str | None = None,
        slug: str | None = None,
        icon: str | None = None,
        description: str | None = None,
        sort_order: int | None = None,
        is_active: bool | None = None,
    ) -> Category | None:
        fields: list[str] = []
        params: list[object] = []
        if name is not None:
            fields.append("name = %s")
            params.append(name.strip())
            fields.append("slug = %s")
            params.append(slug or _slugify(name))
        elif slug is not None:
            fields.append("slug = %s")
            params.append(slug)
        if icon is not None:
            fields.append("icon = %s")
            params.append((icon or "CAT")[:16])
        if description is not None:
            fields.append("description = %s")
            params.append(description)
        if sort_order is not None:
            fields.append("sort_order = %s")
            params.append(int(sort_order))
        if is_active is not None:
            fields.append("is_active = %s")
            params.append(bool(is_active))
        if not fields:
            return self.find_by_id(category_id)
        params.append(category_id)
        with self._db() as db:
            db.execute(
                f"UPDATE categories SET {', '.join(fields)} WHERE id = %s",
                tuple(params),
            )
            row = db.fetch_one("SELECT * FROM categories WHERE id = %s", (category_id,))
        return Category.from_row(row)

    def delete(self, category_id: int) -> bool:
        from app.exceptions import CategoryInUseError

        with self._db() as db:
            row = db.fetch_one(
                "SELECT COUNT(*) AS count FROM skills WHERE category_id = %s",
                (category_id,),
            )
        if int((row or {}).get("count") or 0) > 0:
            raise CategoryInUseError(category_id)
        with self._db() as db:
            db.execute("DELETE FROM categories WHERE id = %s", (category_id,))
        return True
