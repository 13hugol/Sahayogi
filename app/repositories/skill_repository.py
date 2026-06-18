from __future__ import annotations

from app.models.skill import Category, Skill
from .base_repository import BaseRepository


def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "category"


class CategoryRepository(BaseRepository):
    def find_by_id(self, category_id: int) -> Category | None:
        with self._db() as db:
            row = db.fetch_one("SELECT * FROM categories WHERE id = %s", (category_id,))
        return Category.from_row(row)

    def find_by_name(self, name: str) -> Category | None:
        with self._db() as db:
            row = db.fetch_one("SELECT * FROM categories WHERE name = %s", (name.strip(),))
        return Category.from_row(row)

    def find_by_slug(self, slug: str) -> Category | None:
        with self._db() as db:
            row = db.fetch_one("SELECT * FROM categories WHERE slug = %s", (slug.strip(),))
        return Category.from_row(row)

    def all(self) -> list[Category]:
        with self._db() as db:
            rows = db.fetch_all(
                """
                SELECT *
                FROM categories
                WHERE is_active = TRUE
                ORDER BY sort_order ASC, name ASC
                """
            )
        return [cat for r in rows if (cat := Category.from_row(r))]

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
        slug = _slugify(name)
        with self._db() as db:
            cat_id = db.execute(
                """
                INSERT INTO categories (name, description, slug, icon, sort_order, is_active)
                VALUES (%s, %s, %s, %s, %s, TRUE)
                """,
                (name.strip(), description, slug, icon[:8] or "CAT", sort_order),
            )
        return self.find_by_id(cat_id)

    def create(
        self,
        name: str,
        description: str | None = None,
        icon: str = "CAT",
        sort_order: int = 0,
        is_active: bool = True,
    ) -> Category:
        slug = _slugify(name)
        with self._db() as db:
            cat_id = db.execute(
                """
                INSERT INTO categories (name, description, slug, icon, sort_order, is_active)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (name.strip(), description, slug, icon[:8] or "CAT", sort_order, bool(is_active)),
            )
        return self.find_by_id(cat_id)

    def update(
        self,
        category_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        icon: str | None = None,
        sort_order: int | None = None,
        is_active: bool | None = None,
    ) -> Category | None:
        existing = self.find_by_id(category_id)
        if not existing:
            return None
        fields: list[str] = []
        params: list[object] = []
        if name is not None:
            fields.append("name = %s")
            params.append(name.strip())
            fields.append("slug = %s")
            params.append(_slugify(name))
        if description is not None:
            fields.append("description = %s")
            params.append(description)
        if icon is not None:
            fields.append("icon = %s")
            params.append(icon[:8] or "CAT")
        if sort_order is not None:
            fields.append("sort_order = %s")
            params.append(int(sort_order))
        if is_active is not None:
            fields.append("is_active = %s")
            params.append(bool(is_active))
        if not fields:
            return existing
        params.append(category_id)
        with self._db() as db:
            db.execute(
                f"UPDATE categories SET {', '.join(fields)} WHERE id = %s",
                tuple(params),
            )
        return self.find_by_id(category_id)

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
            rows_affected = db.execute(
                "DELETE FROM categories WHERE id = %s",
                (category_id,),
            )
        return rows_affected > 0


class SkillRepository(BaseRepository):
    def find_by_id(self, skill_id: int) -> Skill | None:
        with self._db() as db:
            row = db.fetch_one("SELECT * FROM skills WHERE id = %s", (skill_id,))
        return Skill.from_row(row)

    def find_by_user_id(self, user_id: int) -> list[Skill]:
        with self._db() as db:
            rows = db.fetch_all("SELECT * FROM skills WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
        return [s for row in rows if (s := Skill.from_row(row))]

    def find_by_status(self, status: str) -> list[Skill]:
        with self._db() as db:
            rows = db.fetch_all("SELECT * FROM skills WHERE status = %s ORDER BY created_at DESC", (status,))
        return [s for row in rows if (s := Skill.from_row(row))]

    def create(
        self,
        *,
        user_id: int,
        category_id: int,
        skill_id: int,
        title: str,
        description: str,
        exchange_type: str,
        credit_cost: int,
        availability: str,
        location_text: str | None = None,
        contact_method: str | None = None,
        status: str = "pending",
        certificate_path: str | None = None,
        certificate_status: str = "none",
    ) -> Skill:
        with self._db() as db:
            inserted_id = db.execute(
                """
                INSERT INTO skills (
                    user_id, category_id, skill_id, title, description, exchange_type,
                    credit_cost, availability, location_text, contact_method, status, 
                    certificate_path, certificate_status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    category_id,
                    skill_id,
                    title,
                    description,
                    exchange_type,
                    credit_cost,
                    availability,
                    location_text,
                    contact_method,
                    status,
                    certificate_path,
                    certificate_status,
                ),
            )
            row = db.fetch_one("SELECT * FROM skills WHERE id = %s", (inserted_id,))
        return Skill.from_row(row)

    def update(self, skill: Skill) -> None:
        with self._db() as db:
            db.execute(
                """
                UPDATE skills
                SET category_id = %s,
                    skill_id = %s,
                    title = %s,
                    description = %s,
                    exchange_type = %s,
                    credit_cost = %s,
                    availability = %s,
                    location_text = %s,
                    contact_method = %s,
                    status = %s,
                    rejection_reason = %s,
                    certificate_path = %s,
                    certificate_status = %s
                WHERE id = %s
                """,
                (
                    skill.category_id,
                    skill.skill_id,
                    skill.title,
                    skill.description,
                    skill.exchange_type,
                    skill.credit_cost,
                    skill._availability_raw,
                    skill.location_text,
                    skill.contact_method,
                    skill.status,
                    skill.rejection_reason,
                    skill.certificate_path,
                    skill.certificate_status,
                    skill.id,
                ),
            )

    def update_certificate_info(self, skill_id: int, certificate_path: str | None, certificate_status: str) -> None:
        with self._db() as db:
            db.execute(
                """
                UPDATE skills
                SET certificate_path = %s, certificate_status = %s
                WHERE id = %s
                """,
                (certificate_path, certificate_status, skill_id),
            )

    def update_certificate_info_by_skill_id(self, user_id: int, skill_id: int, certificate_path: str | None, certificate_status: str) -> None:
        with self._db() as db:
            db.execute(
                """
                UPDATE skills
                SET certificate_path = %s, certificate_status = %s
                WHERE user_id = %s AND skill_id = %s
                """,
                (certificate_path, certificate_status, user_id, skill_id),
            )

    def delete(self, skill_id: int) -> bool:
        with self._db() as db:
            rows_affected = db.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
        return rows_affected > 0

    def search(
        self,
        query: str | None = None,
        category_id: int | None = None,
        exchange_type: str | None = None,
        status: str | None = "approved",
    ) -> list[Skill]:
        sql = "SELECT * FROM skills WHERE 1=1"
        params = []
        if status:
            sql += " AND status = %s"
            params.append(status)
        if category_id is not None:
            sql += " AND category_id = %s"
            params.append(category_id)
        if exchange_type:
            sql += " AND exchange_type = %s"
            params.append(exchange_type)
        if query:
            sql += " AND (title LIKE %s OR description LIKE %s)"
            like_query = f"%{query}%"
            params.append(like_query)
            params.append(like_query)
        sql += " ORDER BY created_at DESC"
        with self._db() as db:
            rows = db.fetch_all(sql, params)
        return [s for row in rows if (s := Skill.from_row(row))]

    def deactivate_all_for_user(self, user_id: int) -> None:
        with self._db() as db:
            db.execute(
                "UPDATE skills SET status = 'deactivated' WHERE user_id = %s",
                (user_id,),
            )
