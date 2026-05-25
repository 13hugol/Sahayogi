from __future__ import annotations

from app.models.skill import Category, Skill
from .base_repository import BaseRepository


class CategoryRepository(BaseRepository):
    def find_by_id(self, category_id: int) -> Category | None:
        with self._db() as db:
            row = db.fetch_one("SELECT * FROM categories WHERE id = %s", (category_id,))
        return Category.from_row(row)

    def find_by_name(self, name: str) -> Category | None:
        with self._db() as db:
            row = db.fetch_one("SELECT * FROM categories WHERE name = %s", (name.strip(),))
        return Category.from_row(row)

    def all(self) -> list[Category]:
        with self._db() as db:
            rows = db.fetch_all("SELECT * FROM categories ORDER BY name ASC")
        return [cat for r in rows if (cat := Category.from_row(r))]

    def ensure(self, name: str, description: str | None = None) -> Category:
        existing = self.find_by_name(name)
        if existing:
            return existing
        with self._db() as db:
            cat_id = db.execute(
                "INSERT INTO categories (name, description) VALUES (%s, %s)",
                (name.strip(), description),
            )
        return Category(id=cat_id, name=name.strip(), description=description)


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
