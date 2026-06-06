from __future__ import annotations

from dataclasses import dataclass

from app.models import ProfileCertificate, ProfileReview, User


@dataclass(frozen=True)
class RegistrationData:
    full_name: str
    email: str
    location: str
    password: str
    confirm_password: str

    @property
    def values(self) -> dict[str, str]:
        return {
            "full_name": self.full_name,
            "email": self.email,
            "location": self.location,
        }


@dataclass(frozen=True)
class LoginData:
    email: str
    password: str


@dataclass(frozen=True)
class PasswordResetRequestData:
    email: str


@dataclass(frozen=True)
class PasswordResetData:
    password: str
    confirm_password: str


@dataclass(frozen=True)
class PasswordChangeData:
    current_password: str
    password: str
    confirm_password: str


@dataclass(frozen=True)
class DashboardStats:
    total_users: int
    admin_users: int
    regular_users: int
    verified_users: int
    audit_logs: int


@dataclass(frozen=True)
class ProfilePageData:
    user: User
    approved_certificates: list[ProfileCertificate]
    recent_reviews: list[ProfileReview]
    approved_listings: list[object]


@dataclass(frozen=True)
class TopRatedProfile:
    user_id: int
    full_name: str
    username: str
    reputation_score: float
    review_count: int
    completed_exchange_count: int


@dataclass(frozen=True)
class MutualSkillMatch:
    user: User
    my_offers_they_want: tuple[str, ...]
    their_offers_i_want: tuple[str, ...]
    relevance_score: int
    is_new: bool = False

    @property
    def summary(self) -> str:
        offer = ", ".join(self.my_offers_they_want) or "your skills"
        want = ", ".join(self.their_offers_i_want) or "their skills"
        return f"You can help with {offer}. They can help with {want}."

    @property
    def overlap_count(self) -> int:
        return len(self.my_offers_they_want) + len(self.their_offers_i_want)

