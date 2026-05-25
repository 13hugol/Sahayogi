from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace

from .base_model import BaseModel


@dataclass
class Category(BaseModel):
    id: int
    name: str
    description: str | None = None

    @classmethod
    def from_row(cls, row: dict | None) -> Category | None:
        if not row:
            return None
        return cls(
            id=row["id"],
            name=row["name"],
            description=row.get("description"),
        )

    @classmethod
    def find_by_id(cls, category_id: int) -> Category | None:
        from app.repositories import CategoryRepository

        return CategoryRepository().find_by_id(category_id)

    @classmethod
    def find_by_name(cls, name: str) -> Category | None:
        from app.repositories import CategoryRepository

        return CategoryRepository().find_by_name(name)

    @classmethod
    def all(cls) -> list[Category]:
        from app.repositories import CategoryRepository

        return CategoryRepository().all()


@dataclass
class Skill(BaseModel):
    id: int
    user_id: int
    category_id: int
    skill_id: int
    title: str
    description: str
    exchange_type: str
    credit_cost: int
    _availability_raw: str
    status: str
    location_text: str | None = None
    contact_method: str | None = None
    rejection_reason: str | None = None
    certificate_path: str | None = None
    certificate_status: str = "none"
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_row(cls, row: dict | None) -> Skill | None:
        if not row:
            return None
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            category_id=row["category_id"],
            skill_id=row["skill_id"],
            title=row["title"],
            description=row["description"],
            exchange_type=row.get("exchange_type", "credit"),
            credit_cost=int(row.get("credit_cost", 10)),
            _availability_raw=row["availability"],
            status=row.get("status", "pending"),
            location_text=row.get("location_text"),
            contact_method=row.get("contact_method"),
            rejection_reason=row.get("rejection_reason"),
            certificate_path=row.get("certificate_path"),
            certificate_status=row.get("certificate_status", "none"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    @property
    def user(self):
        from app.models.user import User

        return User.find_by_id(self.user_id)

    @property
    def category(self):
        return Category.find_by_id(self.category_id)

    @property
    def availability(self) -> list[SimpleNamespace]:
        lines = (self._availability_raw or "").split("\n")
        res = []
        for line in lines:
            line = line.strip()
            if line:
                res.append(SimpleNamespace(label=line))
        return res

    @property
    def skill(self):
        from app.database import Database

        db = Database()
        try:
            row = db.fetch_one("SELECT * FROM profile_skills WHERE id = %s", (self.skill_id,))
            if row:
                return SimpleNamespace(id=row["id"], name=row["skill_name"])
        finally:
            db.close()
        return None

    @classmethod
    def find_by_id(cls, skill_id: int) -> Skill | None:
        from app.repositories import SkillRepository

        return SkillRepository().find_by_id(skill_id)

    @classmethod
    def find_by_user_id(cls, user_id: int) -> list[Skill]:
        from app.repositories import SkillRepository

        return SkillRepository().find_by_user_id(user_id)
