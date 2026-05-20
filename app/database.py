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

    def fetch_one(self, query: str, params: Iterable[Any] | None = None) -> dict | None:
        cursor = self.__connection.cursor()
        cursor.execute(query, params)
        result = cursor.fetchone()
        cursor.close()
        return result

    def fetch_all(self, query: str, params: Iterable[Any] | None = None) -> list[dict]:
        cursor = self.__connection.cursor()
        cursor.execute(query, params)
        results = cursor.fetchall()
        cursor.close()
        return list(results)

    def execute(self, query: str, params: Iterable[Any] | None = None) -> int:
        cursor = self.__connection.cursor()
        cursor.execute(query, params)
        self.__connection.commit()
        lastrowid = cursor.lastrowid
        cursor.close()
        return int(lastrowid or 0)

    def execute_many(self, query: str, params: Iterable[Iterable[Any]]) -> None:
        cursor = self.__connection.cursor()
        cursor.executemany(query, params)
        self.__connection.commit()
        cursor.close()

    def close(self) -> None:
        self.__connection.close()

    @contextmanager
    def transaction(self):
        try:
            yield self
            self.__connection.commit()
        except Exception:
            self.__connection.rollback()
            raise

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
                reputation_score FLOAT NOT NULL DEFAULT 0,
                review_count INT NOT NULL DEFAULT 0,
                completed_exchange_count INT NOT NULL DEFAULT 0,
                CONSTRAINT fk_profiles_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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
        finally:
            db.close()
