from __future__ import annotations

from app.dto import ProfilePageData
from app.exceptions import ProfileNotFoundError
from app.repositories import (
    ProfileCertificateRepository,
    ProfileRepository,
    ProfileReviewRepository,
    UserRepository,
)


class ProfileService:
    def __init__(
        self,
        user_repository: UserRepository,
        profile_repository: ProfileRepository,
        certificate_repository: ProfileCertificateRepository,
        review_repository: ProfileReviewRepository,
    ):
        self._user_repository = user_repository
        self._profile_repository = profile_repository
        self._certificate_repository = certificate_repository
        self._review_repository = review_repository

    def get_profile_page_data(self, user_id: int) -> ProfilePageData:
        user = self._user_repository.find_by_id(user_id)
        if not user or not user.profile:
            raise ProfileNotFoundError(user_id)
        return ProfilePageData(
            user=user,
            approved_certificates=self._certificate_repository.approved_for_user(user.id),
            recent_reviews=self._review_repository.recent_for_user(user.id),
            approved_listings=[],
        )

    def get_review_history(self, user_id: int, *, page: int = 1, per_page: int = 10):
        user = self._user_repository.find_by_id(user_id)
        if not user or not user.profile:
            raise ProfileNotFoundError(user_id)
        reviews = self._review_repository.for_user(user.id, page=page, per_page=per_page)
        total = self._review_repository.count_for_user(user.id)
        return user, reviews, total

    def get_top_rated_profiles(self, limit: int = 12):
        return self._profile_repository.top_rated(limit)

<<<<<<< HEAD
    def delete_account(self, user_id: int) -> None:
        user = self._user_repository.find_by_id(user_id)
        if not user:
            return
        recipient_email = user.email

        # 1. Fetch file paths before database cleanup
        with self._user_repository._db() as db:
            avatar_row = db.fetch_one("SELECT avatar_path FROM profiles WHERE user_id = %s", (user_id,))
            cert_rows = db.fetch_all("SELECT file_path FROM profile_certificates WHERE user_id = %s", (user_id,))
            skill_cert_rows = db.fetch_all("SELECT certificate_path FROM skills WHERE user_id = %s", (user_id,))

        # 2. Perform database anonymization and deletion
        self._user_repository.anonymize_and_cleanup_user_data(user_id)

        # 3. Clean up physical files from disk
        from flask import current_app
        from pathlib import Path

        upload_folder = current_app.config.get("UPLOAD_FOLDER")
        if upload_folder:
            # Delete avatar
            if avatar_row and avatar_row.get("avatar_path"):
                avatar_path = Path(upload_folder) / avatar_row["avatar_path"]
                if avatar_path.is_file():
                    try:
                        avatar_path.unlink()
                    except OSError:
                        pass

            # Delete profile certificates
            for row in cert_rows:
                if row.get("file_path"):
                    cert_path = Path(upload_folder) / row["file_path"]
                    if cert_path.is_file():
                        try:
                            cert_path.unlink()
                        except OSError:
                            pass

            # Delete skill listing certificates
            for row in skill_cert_rows:
                if row.get("certificate_path"):
                    skill_cert_path = Path(upload_folder) / row["certificate_path"]
                    if skill_cert_path.is_file():
                        try:
                            skill_cert_path.unlink()
                        except OSError:
                            pass

        # 4. Send final confirmation email
        from app.utils.email import send_email
        send_email(
            "Account Deletion Confirmed",
            recipient_email,
            "Dear User,\n\nThis email confirms that your account and all associated personal data have been permanently deleted from our platform in accordance with your request and GDPR regulations.\n\nThank you for being a part of our community.\n\nBest regards,\nThe Sahayogi Team"
        )

    def save_location_coords(self, user_id: int, latitude: float, longitude: float, location_label: str) -> None:
        self._profile_repository.save_location_coords(user_id, latitude, longitude, location_label)

