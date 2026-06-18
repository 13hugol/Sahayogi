from __future__ import annotations

from app.models.skill import Category, Skill
from app.repositories import CategoryRepository, SkillRepository


class SkillService:
    def __init__(self, skill_repository: SkillRepository, category_repository: CategoryRepository):
        self._skill_repository = skill_repository
        self._category_repository = category_repository

    def create_listing(
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
        return self._skill_repository.create(
            user_id=user_id,
            category_id=category_id,
            skill_id=skill_id,
            title=title,
            description=description,
            exchange_type=exchange_type,
            credit_cost=credit_cost,
            availability=availability,
            location_text=location_text,
            contact_method=contact_method,
            status=status,
            certificate_path=certificate_path,
            certificate_status=certificate_status,
        )

    def edit_listing(
        self,
        listing_id: int,
        *,
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
    ) -> Skill | None:
        skill = self._skill_repository.find_by_id(listing_id)
        if not skill:
            return None
        skill.category_id = category_id
        skill.skill_id = skill_id
        skill.title = title
        skill.description = description
        skill.exchange_type = exchange_type
        skill.credit_cost = credit_cost
        skill._availability_raw = availability
        skill.location_text = location_text
        skill.contact_method = contact_method
        skill.status = status
        self._skill_repository.update(skill)
        return skill

    def delete_listing(self, skill_id: int) -> bool:
        return self._skill_repository.delete(skill_id)

    def get_listing_by_id(self, skill_id: int) -> Skill | None:
        return self._skill_repository.find_by_id(skill_id)

    def get_listings_by_user(self, user_id: int) -> list[Skill]:
        return self._skill_repository.find_by_user_id(user_id)

    def search_listings(
        self,
        query: str | None = None,
        category_id: int | None = None,
        exchange_type: str | None = None,
        status: str | None = "approved",
    ) -> list[Skill]:
        return self._skill_repository.search(query, category_id, exchange_type, status)

    def search_listings_by_location(
        self,
        user_lat: float,
        user_lng: float,
        radius_km: int,
        query: str | None = None,
        category_ids: list[int] | None = None,
        exchange_type: str | None = None,
        status: str | None = "approved",
    ) -> list[Skill]:
        return self._skill_repository.search_by_location(
            user_lat, user_lng, radius_km, query, category_ids, exchange_type, status
        )

    def get_all_categories(self) -> list[Category]:
        return self._category_repository.all()

    def get_category_by_id(self, category_id: int) -> Category | None:
        return self._category_repository.find_by_id(category_id)
