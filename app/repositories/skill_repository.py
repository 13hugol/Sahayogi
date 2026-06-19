from __future__ import annotations

from app.models.skill import Category, Skill
from .base_repository import BaseRepository



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

    def search_by_location(
        self,
        user_lat: float,
        user_lng: float,
        radius_km: int,
        query: str | None = None,
        category_ids: list[int] | None = None,
        exchange_type: str | None = None,
        status: str | None = "approved",
    ) -> list[Skill]:
        params: list[object] = [user_lat, user_lng, user_lat]
        sql = """
            SELECT s.*, 
            (
                6371 * ACOS(
                    COS(RADIANS(%s)) * COS(RADIANS(p.latitude))
                    * COS(RADIANS(p.longitude) - RADIANS(%s))
                    + SIN(RADIANS(%s)) * SIN(RADIANS(p.latitude))
                )
            ) AS distance_km
            FROM skills s
            JOIN users u ON s.user_id = u.id
            JOIN profiles p ON s.user_id = p.user_id
            WHERE p.latitude IS NOT NULL AND p.longitude IS NOT NULL
        """
        if status:
            sql += " AND s.status = %s"
            params.append(status)
        if exchange_type:
            sql += " AND s.exchange_type = %s"
            params.append(exchange_type)
        if category_ids:
            placeholders = ", ".join(["%s"] * len(category_ids))
            sql += f" AND s.category_id IN ({placeholders})"
            params.extend(category_ids)
        if query:
            sql += " AND (s.title LIKE %s OR s.description LIKE %s)"
            like_query = f"%{query}%"
            params.extend([like_query, like_query])
            
        sql += " HAVING distance_km <= %s ORDER BY distance_km ASC"
        params.append(radius_km)
        
        with self._db() as db:
            rows = db.fetch_all(sql, params)
        
        results = []
        for row in rows:
            skill = Skill.from_row(row)
            if skill:
                skill.distance = row.get("distance_km")
                results.append(skill)
        return results
