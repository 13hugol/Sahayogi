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
                suspended_until DATETIME,
                suspension_reason TEXT,
                failed_login_count INT NOT NULL DEFAULT 0,
                locked_until DATETIME,
                role_id INT NOT NULL,
                credit_balance INT NOT NULL DEFAULT 100,
                last_active_at DATETIME DEFAULT NULL,
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
                reputation_score DECIMAL(3,1) DEFAULT NULL,
                review_count INT NOT NULL DEFAULT 0,
                score_updated_at DATETIME DEFAULT NULL,
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
            CREATE TABLE IF NOT EXISTS categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(80) NOT NULL UNIQUE,
                slug VARCHAR(100) NOT NULL UNIQUE,
                icon VARCHAR(16) NOT NULL DEFAULT 'CAT',
                description VARCHAR(255),
                sort_order INT NOT NULL DEFAULT 0,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX ix_categories_active_order (is_active, sort_order, name)
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
                exchange_id INT,
                reviewee_user_id INT NOT NULL,
                reviewer_id INT,
                reviewer_name VARCHAR(120) NOT NULL,
                rating TINYINT NOT NULL,
                comment TEXT,
                exchange_id INT DEFAULT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_profile_reviews_exchange_reviewer (exchange_id, reviewer_id),
                INDEX ix_profile_reviews_exchange (exchange_id),
                INDEX ix_profile_reviews_reviewee_created (reviewee_user_id, created_at),
                UNIQUE KEY uq_profile_reviews_exchange_reviewer (exchange_id, reviewer_id),
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
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(80) NOT NULL UNIQUE,
                description VARCHAR(255)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS skills (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                category_id INT NOT NULL,
                skill_id INT NOT NULL,
                title VARCHAR(120) NOT NULL,
                description TEXT NOT NULL,
                exchange_type VARCHAR(32) NOT NULL DEFAULT 'credit',
                credit_cost INT NOT NULL DEFAULT 10,
                availability VARCHAR(255) NOT NULL,
                location_text VARCHAR(160),
                contact_method VARCHAR(255),
                status VARCHAR(32) NOT NULL DEFAULT 'pending',
                rejection_reason TEXT,
                certificate_path VARCHAR(255),
                certificate_status VARCHAR(32) NOT NULL DEFAULT 'none',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                CONSTRAINT fk_skills_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT fk_skills_category FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
                CONSTRAINT fk_skills_profile_skill FOREIGN KEY (skill_id) REFERENCES profile_skills(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                event_type VARCHAR(40) NOT NULL DEFAULT 'general',
                title VARCHAR(160) NOT NULL DEFAULT '',
                body TEXT NOT NULL,
                message TEXT,
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
            CREATE TABLE IF NOT EXISTS message_conversations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                subject VARCHAR(160) NOT NULL,
                permission_source VARCHAR(32) NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX ix_message_conversations_updated (updated_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS message_participants (
                conversation_id INT NOT NULL,
                user_id INT NOT NULL,
                last_read_at DATETIME,
                joined_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (conversation_id, user_id),
                INDEX ix_message_participants_user (user_id),
                CONSTRAINT fk_message_participants_conversation FOREIGN KEY (conversation_id) REFERENCES message_conversations(id) ON DELETE CASCADE,
                CONSTRAINT fk_message_participants_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS message_posts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                conversation_id INT NOT NULL,
                sender_id INT NOT NULL,
                body VARCHAR(2000) NOT NULL,
                delivered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                read_at DATETIME,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX ix_message_posts_conversation_created (conversation_id, created_at),
                INDEX ix_message_posts_sender (sender_id),
                CONSTRAINT fk_message_posts_conversation FOREIGN KEY (conversation_id) REFERENCES message_conversations(id) ON DELETE CASCADE,
                CONSTRAINT fk_message_posts_sender FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS exchange_requests (
                id INT AUTO_INCREMENT PRIMARY KEY,
                listing_id INT NOT NULL,
                learner_id INT NOT NULL,
                offered_skill_id INT DEFAULT NULL,
                requested_message TEXT DEFAULT NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'pending',
                decline_reason TEXT DEFAULT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                CONSTRAINT fk_exchange_requests_listing FOREIGN KEY (listing_id) REFERENCES skills(id) ON DELETE CASCADE,
                CONSTRAINT fk_exchange_requests_learner FOREIGN KEY (learner_id) REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT fk_exchange_requests_offered_skill FOREIGN KEY (offered_skill_id) REFERENCES profile_skills(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS exchanges (
                id INT AUTO_INCREMENT PRIMARY KEY,
                request_id INT NOT NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'active',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME DEFAULT NULL,
                learner_completed_at DATETIME DEFAULT NULL,
                teacher_completed_at DATETIME DEFAULT NULL,
                video_session_summary TEXT DEFAULT NULL,
                video_call_active BOOLEAN NOT NULL DEFAULT FALSE,
                video_call_started_at DATETIME DEFAULT NULL,
                video_call_ended_at DATETIME DEFAULT NULL,
                CONSTRAINT fk_exchanges_request FOREIGN KEY (request_id) REFERENCES exchange_requests(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS exchange_completion_marks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                exchange_id INT NOT NULL,
                user_id INT NOT NULL,
                completed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_exchange_completion_user (exchange_id, user_id),
                INDEX ix_exchange_completion_exchange (exchange_id),
                CONSTRAINT fk_exchange_completion_exchange FOREIGN KEY (exchange_id) REFERENCES exchanges(id) ON DELETE CASCADE,
                CONSTRAINT fk_exchange_completion_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INT AUTO_INCREMENT PRIMARY KEY,
                reporter_id INT NOT NULL,
                reported_user_id INT NOT NULL,
                reason VARCHAR(64) NOT NULL,
                description TEXT DEFAULT NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'open',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                CONSTRAINT fk_reports_reporter FOREIGN KEY (reporter_id) REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT fk_reports_reported_user FOREIGN KEY (reported_user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS credit_transactions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                amount_delta INT NOT NULL,
                entry_type VARCHAR(50) NOT NULL,
                description VARCHAR(255) NOT NULL,
                skill_id INT DEFAULT NULL,
                exchange_id INT DEFAULT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_credit_transactions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT fk_credit_transactions_skill FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE SET NULL,
                CONSTRAINT fk_credit_transactions_exchange FOREIGN KEY (exchange_id) REFERENCES exchanges(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            """
            CREATE TABLE IF NOT EXISTS credit_holds (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                request_id INT NOT NULL,
                amount INT NOT NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'active',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_credit_holds_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT fk_credit_holds_request FOREIGN KEY (request_id) REFERENCES exchange_requests(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
        ]
        try:
            for statement in statements:
                db.execute(statement)
            for statement, duplicate_codes in (
                ("ALTER TABLE profile_reviews ADD COLUMN exchange_id INT NULL AFTER id", {1060}),
                (
                    "ALTER TABLE profile_reviews ADD UNIQUE KEY uq_profile_reviews_exchange_reviewer (exchange_id, reviewer_id)",
                    {1061},
                ),
                ("ALTER TABLE profile_reviews ADD INDEX ix_profile_reviews_exchange (exchange_id)", {1061}),
                (
                    "ALTER TABLE profile_reviews ADD CONSTRAINT fk_profile_reviews_exchange "
                    "FOREIGN KEY (exchange_id) REFERENCES exchanges(id) ON DELETE CASCADE",
                    {1061, 1826},
                ),
            ):
                try:
                    db.execute(statement)
                except pymysql.err.OperationalError as exc:
                    if exc.args and exc.args[0] in duplicate_codes:
                        continue
                    raise
            for statement, duplicate_code in (
                ("ALTER TABLE categories ADD COLUMN slug VARCHAR(100)", 1060),
                ("ALTER TABLE categories ADD COLUMN icon VARCHAR(16) NOT NULL DEFAULT 'CAT'", 1060),
                ("ALTER TABLE categories ADD COLUMN description VARCHAR(255)", 1060),
                ("ALTER TABLE categories ADD COLUMN sort_order INT NOT NULL DEFAULT 0", 1060),
                ("ALTER TABLE categories ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE", 1060),
                ("ALTER TABLE categories ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP", 1060),
                (
                    "ALTER TABLE categories ADD COLUMN updated_at DATETIME NOT NULL "
                    "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
                    1060,
                ),
                ("ALTER TABLE categories ADD UNIQUE INDEX uq_categories_name (name)", 1061),
                ("ALTER TABLE categories ADD UNIQUE INDEX uq_categories_slug (slug)", 1061),
                ("ALTER TABLE categories ADD INDEX ix_categories_active_order (is_active, sort_order, name)", 1061),
            ):
                try:
                    db.execute(statement)
                except pymysql.err.OperationalError as exc:
                    if exc.args and exc.args[0] == duplicate_code:
                        continue
                    raise
            db.execute(
                """
                UPDATE categories
                SET slug = LOWER(REGEXP_REPLACE(name, '[^A-Za-z0-9]+', '-'))
                WHERE slug IS NULL OR slug = ''
                """
            )
            db.execute(
                """
                UPDATE categories
                SET icon = LEFT(UPPER(REGEXP_REPLACE(name, '[^A-Za-z0-9]+', '')), 16)
                WHERE icon IS NULL OR icon = '' OR icon = 'CAT'
                """
            )
            db.execute(
                """
                UPDATE categories
                SET description = ''
                WHERE description IS NULL
                """
            )
            db.execute(
                """
                UPDATE categories
                SET sort_order = CASE id
                    WHEN 1 THEN 1
                    WHEN 2 THEN 2
                    WHEN 3 THEN 3
                    WHEN 4 THEN 4
                    ELSE sort_order
                END
                WHERE id IN (1, 2, 3, 4) AND sort_order = 0
                """
            )
            db.execute(
                """
                UPDATE categories
                SET icon = CASE id
                    WHEN 1 THEN 'TECH'
                    WHEN 2 THEN 'MUS'
                    WHEN 3 THEN 'LANG'
                    WHEN 4 THEN 'KIT'
                    ELSE icon
                END
                WHERE id IN (1, 2, 3, 4)
                  AND icon IN ('CAT', 'TECH', 'MUSIC', 'LANGUAGE', 'KITCHEN')
                """
            )
            from app.repositories.category_repository import CategoryRepository

            CategoryRepository().seed_defaults()
            Database.seed_search_listing_examples(db)
            for statement in (
                "ALTER TABLE profiles ADD COLUMN headline VARCHAR(160)",
                "ALTER TABLE profiles ADD COLUMN bio TEXT",
                "ALTER TABLE profiles MODIFY COLUMN reputation_score DECIMAL(3,1) DEFAULT NULL",
                "ALTER TABLE profiles ADD COLUMN score_updated_at DATETIME DEFAULT NULL",
                "ALTER TABLE notifications ADD COLUMN event_type VARCHAR(40) NOT NULL DEFAULT 'general'",
                "ALTER TABLE notifications ADD COLUMN title VARCHAR(160) NOT NULL DEFAULT ''",
                "ALTER TABLE notifications ADD COLUMN body TEXT",
                "ALTER TABLE notifications ADD COLUMN target_url VARCHAR(255)",
                "ALTER TABLE notifications ADD COLUMN read_at DATETIME",
                "ALTER TABLE notifications ADD INDEX ix_notifications_user_read_created (user_id, is_read, created_at)",
                "ALTER TABLE notifications ADD INDEX ix_notifications_event_type (event_type)",
                "ALTER TABLE categories ADD COLUMN slug VARCHAR(80)",
                "ALTER TABLE categories ADD COLUMN icon VARCHAR(8) NOT NULL DEFAULT 'CAT'",
                "ALTER TABLE categories ADD COLUMN sort_order INT NOT NULL DEFAULT 0",
                "ALTER TABLE categories ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE",
                "ALTER TABLE categories ADD UNIQUE KEY uq_categories_slug (slug)",
                "ALTER TABLE users ADD COLUMN suspended_until DATETIME",
                "ALTER TABLE users ADD COLUMN suspension_reason TEXT",
                "ALTER TABLE users ADD COLUMN credit_balance INT NOT NULL DEFAULT 100",
                "ALTER TABLE exchanges ADD COLUMN learner_completed_at DATETIME DEFAULT NULL",
                "ALTER TABLE exchanges ADD COLUMN teacher_completed_at DATETIME DEFAULT NULL",
                "ALTER TABLE profile_reviews ADD COLUMN exchange_id INT DEFAULT NULL",
                "ALTER TABLE profile_reviews ADD UNIQUE KEY uq_profile_reviews_exchange_reviewer (exchange_id, reviewer_id)",
                "ALTER TABLE users ADD COLUMN last_active_at DATETIME DEFAULT NULL",
                "ALTER TABLE exchanges ADD COLUMN video_call_active BOOLEAN NOT NULL DEFAULT FALSE",
                "ALTER TABLE exchanges ADD COLUMN video_call_started_at DATETIME DEFAULT NULL",
                "ALTER TABLE exchanges ADD COLUMN video_call_ended_at DATETIME DEFAULT NULL",
            ):
                try:
                    db.execute(statement)
                except pymysql.err.OperationalError as exc:
                    if exc.args and exc.args[0] in {1060, 1061, 1091}:
                        continue
                    raise
            Database._backfill_notifications(db)
            Database._backfill_categories(db)
        finally:
            db.close()

    @staticmethod
    def _backfill_notifications(db: "Database") -> None:
        try:
            db.execute(
                """
                UPDATE notifications
                SET body = COALESCE(NULLIF(body, ''), message, '')
                WHERE body IS NULL OR body = ''
                """
            )
            db.execute(
                """
                UPDATE notifications
                SET title = COALESCE(NULLIF(title, ''), LEFT(body, 80))
                WHERE title IS NULL OR title = ''
                """
            )
        except pymysql.err.OperationalError:
            return

    @staticmethod
    def _backfill_categories(db: "Database") -> None:
        try:
            db.execute(
                """
                UPDATE categories
                SET slug = LOWER(REPLACE(name, ' ', '-'))
                WHERE slug IS NULL OR slug = ''
                """
            )
        except pymysql.err.OperationalError:
            return

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
