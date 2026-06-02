from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterable

import pymysql
from flask import current_app


class Database:
    def __init__(self):
        self.__connection = pymysql.connect(
            host=current_app.config["MYSQL_HOST"],
            port=current_app.config["MYSQL_PORT"],
            user=current_app.config["MYSQL_USER"],
            password=current_app.config["MYSQL_PASSWORD"],
            database=current_app.config["MYSQL_DATABASE"],
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
            charset="utf8mb4",
        )
        self.__in_transaction = False

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def fetch_one(self, query: str, params: Iterable[Any] | None = None) -> dict | None:
        cursor = self.__connection.cursor()
        try:
            cursor.execute(query, params)
            return cursor.fetchone()
        finally:
            cursor.close()

    def fetch_all(self, query: str, params: Iterable[Any] | None = None) -> list[dict]:
        cursor = self.__connection.cursor()
        try:
            cursor.execute(query, params)
            results = cursor.fetchall()
            return list(results)
        finally:
            cursor.close()

    def execute(self, query: str, params: Iterable[Any] | None = None) -> int:
        cursor = self.__connection.cursor()
        try:
            cursor.execute(query, params)
            if not self.__in_transaction:
                self.__connection.commit()
            return int(cursor.lastrowid or 0)
        finally:
            cursor.close()

    def execute_many(self, query: str, params: Iterable[Iterable[Any]]) -> None:
        cursor = self.__connection.cursor()
        try:
            cursor.executemany(query, params)
            if not self.__in_transaction:
                self.__connection.commit()
        finally:
            cursor.close()

    def close(self) -> None:
        self.__connection.close()

    @contextmanager
    def transaction(self):
        nested = self.__in_transaction
        if not nested:
            self.__in_transaction = True
        try:
            yield self
            if not nested:
                self.__connection.commit()
        except Exception:
            if not nested:
                self.__connection.rollback()
            raise
        finally:
            if not nested:
                self.__in_transaction = False

    @staticmethod
    def create_tables() -> None:
        db = Database()
        statements = [
            """
            CREATE TABLE IF NOT EXISTS roles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(32) NOT NULL UNIQUE,
                description VARCHAR(255)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                full_name VARCHAR(120) NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                is_email_verified BOOLEAN NOT NULL DEFAULT FALSE,
                verification_token VARCHAR(255),
                verification_token_expires DATETIME,
                status VARCHAR(32) NOT NULL DEFAULT 'active',
                failed_login_count INT NOT NULL DEFAULT 0,
                locked_until DATETIME,
                role_id INT NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX ix_users_email (email),
                CONSTRAINT fk_users_role FOREIGN KEY (role_id) REFERENCES roles(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS profiles (
                user_id INT PRIMARY KEY,
                username VARCHAR(64) NOT NULL UNIQUE,
                location VARCHAR(160),
                contact_email VARCHAR(255),
                avatar_path VARCHAR(255),
                headline VARCHAR(160),
                bio TEXT,
                reputation_score FLOAT NOT NULL DEFAULT 0,
                review_count INT NOT NULL DEFAULT 0,
                completed_exchange_count INT NOT NULL DEFAULT 0,
                CONSTRAINT fk_profiles_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                token_hash CHAR(64) NOT NULL UNIQUE,
                expires_at DATETIME NOT NULL,
                used_at DATETIME,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX ix_password_reset_user_used (user_id, used_at),
                INDEX ix_password_reset_expires (expires_at),
                CONSTRAINT fk_password_reset_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS profile_skills (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                skill_name VARCHAR(120) NOT NULL,
                skill_type VARCHAR(16) NOT NULL,
                sort_order INT NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_profile_skill (user_id, skill_name, skill_type),
                INDEX ix_profile_skills_user_type (user_id, skill_type),
                CONSTRAINT fk_profile_skills_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS profile_certificates (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                profile_skill_id INT,
                skill_name VARCHAR(120) NOT NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'pending',
                file_path VARCHAR(255),
                review_notes TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX ix_profile_certificates_user_status (user_id, status),
                CONSTRAINT fk_profile_certificates_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT fk_profile_certificates_skill FOREIGN KEY (profile_skill_id) REFERENCES profile_skills(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS skill_search_listings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(160) NOT NULL,
                skill_name VARCHAR(120) NOT NULL,
                category_id INT,
                category_name VARCHAR(80) NOT NULL,
                provider_name VARCHAR(120) NOT NULL,
                provider_location VARCHAR(160),
                description TEXT NOT NULL,
                exchange_type VARCHAR(16) NOT NULL DEFAULT 'credit',
                min_credits INT NOT NULL DEFAULT 10,
                location_text VARCHAR(160),
                contact_method VARCHAR(120),
                reputation_score FLOAT NOT NULL DEFAULT 0,
                status VARCHAR(32) NOT NULL DEFAULT 'approved',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX ix_skill_search_status_created (status, created_at),
                INDEX ix_skill_search_title (title),
                FULLTEXT KEY ft_skill_search_title_description (title, description)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                event_type VARCHAR(40) NOT NULL,
                title VARCHAR(160) NOT NULL,
                body TEXT NOT NULL,
                target_url VARCHAR(255),
                is_read BOOLEAN NOT NULL DEFAULT FALSE,
                read_at DATETIME,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX ix_notifications_user_read_created (user_id, is_read, created_at),
                INDEX ix_notifications_event_type (event_type),
                CONSTRAINT fk_notifications_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS profile_reviews (
                id INT AUTO_INCREMENT PRIMARY KEY,
                reviewee_user_id INT NOT NULL,
                reviewer_id INT,
                reviewer_name VARCHAR(120) NOT NULL,
                rating TINYINT NOT NULL,
                comment TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX ix_profile_reviews_reviewee_created (reviewee_user_id, created_at),
                CONSTRAINT fk_profile_reviews_reviewee FOREIGN KEY (reviewee_user_id) REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT fk_profile_reviews_reviewer FOREIGN KEY (reviewer_id) REFERENCES users(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS admin_audit_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                admin_id INT NOT NULL,
                action VARCHAR(80) NOT NULL,
                target_type VARCHAR(80) NOT NULL,
                target_id INT,
                detail TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_audit_admin FOREIGN KEY (admin_id) REFERENCES users(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
        ]
        try:
            for statement in statements:
                db.execute(statement)
            Database.seed_search_listing_examples(db)
            for statement in (
                "ALTER TABLE profiles ADD COLUMN headline VARCHAR(160)",
                "ALTER TABLE profiles ADD COLUMN bio TEXT",
            ):
                try:
                    db.execute(statement)
                except pymysql.err.OperationalError as exc:
                    if exc.args and exc.args[0] == 1060:
                        continue
                    raise
        finally:
            db.close()

    @staticmethod
    def seed_search_listing_examples(db: "Database") -> None:
        row = db.fetch_one("SELECT COUNT(*) AS count FROM skill_search_listings")
        if int((row or {}).get("count") or 0) > 0:
            return
        db.execute_many(
            """
            INSERT INTO skill_search_listings (
                title,
                skill_name,
                category_id,
                category_name,
                provider_name,
                provider_location,
                description,
                exchange_type,
                min_credits,
                location_text,
                contact_method,
                reputation_score
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                (
                    "Guitar lessons for beginners",
                    "Guitar",
                    2,
                    "Music",
                    "Aarav Shrestha",
                    "Kathmandu",
                    "Friendly acoustic guitar lessons covering chords, rhythm, and first songs.",
                    "credit",
                    10,
                    "Kathmandu or remote",
                    "In-app messaging",
                    4.7,
                ),
                (
                    "Guitarist jam and stage confidence",
                    "Guitar performance",
                    2,
                    "Music",
                    "Mina Rai",
                    "Lalitpur",
                    "Practice with a guitarist to improve timing, improvisation, and performance confidence.",
                    "teach",
                    0,
                    "Lalitpur",
                    "In-app messaging",
                    4.9,
                ),
                (
                    "Python web basics",
                    "Python",
                    1,
                    "Tech",
                    "Sanjay Thapa",
                    "Bhaktapur",
                    "Learn Python functions, Flask routes, templates, and simple database-backed pages.",
                    "credit",
                    12,
                    "Remote",
                    "In-app messaging",
                    4.5,
                ),
                (
                    "Momo cooking kitchen skills",
                    "Cooking",
                    4,
                    "Kitchen",
                    "Pema Lama",
                    "Kathmandu",
                    "Hands-on momo wrapping, filling preparation, steaming, and achar basics.",
                    "credit",
                    8,
                    "Kathmandu",
                    "In-app messaging",
                    4.6,
                ),
            ),
        )
