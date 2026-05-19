from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
MYSQL_SCHEMES = {"mysql", "mysql+pymysql"}


def validate_mysql_database_url(database_url: str | None, variable_name: str) -> None:
    if not database_url:
        raise RuntimeError(f"{variable_name} environment variable is required. Set it in .env file.")

    scheme = urlsplit(database_url).scheme
    if scheme not in MYSQL_SCHEMES:
        allowed = ", ".join(sorted(MYSQL_SCHEMES))
        raise RuntimeError(f"{variable_name} must use MySQL. Allowed URL schemes: {allowed}.")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_TIME_LIMIT = None
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    UPLOAD_FOLDER = BASE_DIR / "instance" / "uploads"
    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "noreply@sahayogi.local")
    MAIL_LOG_FILE = BASE_DIR / "instance" / "mail.log"
    PAGINATION_PER_PAGE = int(os.getenv("PAGINATION_PER_PAGE", "20"))
    LOCKOUT_THRESHOLD = int(os.getenv("LOCKOUT_THRESHOLD", "10"))
    LOCKOUT_WINDOW_MINUTES = int(os.getenv("LOCKOUT_WINDOW_MINUTES", "10"))
    LOCKOUT_DURATION_MINUTES = int(os.getenv("LOCKOUT_DURATION_MINUTES", "10"))
    PASSWORD_RESET_EXPIRY_SECONDS = int(os.getenv("PASSWORD_RESET_EXPIRY_SECONDS", "1800"))
    INITIAL_CREDITS = int(os.getenv("INITIAL_CREDITS", "10"))
    ACCOUNT_DELETE_GRACE_DAYS = int(os.getenv("ACCOUNT_DELETE_GRACE_DAYS", "30"))
    DEFAULT_ADMIN_EMAIL = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@example.com")
    DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "Admin123!")
    DEFAULT_ADMIN_NAME = os.getenv("DEFAULT_ADMIN_NAME", "Sahayogi Admin")
    BRAND_NAME = "Sahayogi"

    @classmethod
    def validate(cls) -> None:
        validate_mysql_database_url(cls.SQLALCHEMY_DATABASE_URI, "DATABASE_URL")


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL")
    MAIL_SERVER = None
    MAIL_LOG_FILE = BASE_DIR / "instance" / "test-mail.log"

    @classmethod
    def validate(cls) -> None:
        validate_mysql_database_url(cls.SQLALCHEMY_DATABASE_URI, "TEST_DATABASE_URL")
