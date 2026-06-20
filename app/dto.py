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
    avatar_path: str | None = None
    top_category_name: str | None = None
