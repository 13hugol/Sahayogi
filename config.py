from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
MYSQL_SCHEMES = {"mysql", "mysql+pymysql"}


def env_value(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def mail_password() -> str | None:
    password = env_value("MAIL_PASSWORD")
    mail_server = env_value("MAIL_SERVER")
    if password and mail_server and mail_server.lower() == "smtp.gmail.com":
        return password.replace(" ", "")
    return password


def validate_mysql_database_url(database_url: str | None, variable_name: str) -> None:
    if not database_url:
        raise RuntimeError(f"{variable_name} environment variable is required. Set it in .env file.")

    scheme = urlsplit(database_url).scheme
    if scheme not in MYSQL_SCHEMES:
        allowed = ", ".join(sorted(MYSQL_SCHEMES))
        raise RuntimeError(f"{variable_name} must use MySQL. Allowed URL schemes: {allowed}.")


class Config:
    SECRET_KEY = env_value("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = env_value("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_TIME_LIMIT = None
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    UPLOAD_FOLDER = BASE_DIR / "instance" / "uploads"
    MAIL_SERVER = env_value("MAIL_SERVER")
    MAIL_PORT = int(env_value("MAIL_PORT", "587"))
    MAIL_USE_TLS = env_value("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = env_value("MAIL_USERNAME")
    MAIL_PASSWORD = mail_password()
    MAIL_DEFAULT_SENDER = env_value("MAIL_DEFAULT_SENDER", "noreply@sahayogi.local")
    MAIL_LOG_FILE = BASE_DIR / "instance" / "mail.log"
    PAGINATION_PER_PAGE = int(env_value("PAGINATION_PER_PAGE", "20"))
    LOCKOUT_THRESHOLD = int(env_value("LOCKOUT_THRESHOLD", "10"))
    LOCKOUT_WINDOW_MINUTES = int(env_value("LOCKOUT_WINDOW_MINUTES", "10"))
    LOCKOUT_DURATION_MINUTES = int(env_value("LOCKOUT_DURATION_MINUTES", "10"))
    PASSWORD_RESET_EXPIRY_SECONDS = int(env_value("PASSWORD_RESET_EXPIRY_SECONDS", "1800"))
    INITIAL_CREDITS = int(env_value("INITIAL_CREDITS", "10"))
    ACCOUNT_DELETE_GRACE_DAYS = int(env_value("ACCOUNT_DELETE_GRACE_DAYS", "30"))
    DEFAULT_ADMIN_EMAIL = env_value("DEFAULT_ADMIN_EMAIL", "admin@example.com")
    DEFAULT_ADMIN_PASSWORD = env_value("DEFAULT_ADMIN_PASSWORD", "Admin123!")
    DEFAULT_ADMIN_NAME = env_value("DEFAULT_ADMIN_NAME", "Sahayogi Admin")
    BRAND_NAME = "Sahayogi"

    @classmethod
    def validate(cls) -> None:
        validate_mysql_database_url(cls.SQLALCHEMY_DATABASE_URI, "DATABASE_URL")


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = env_value("TEST_DATABASE_URL")
    MAIL_SERVER = None
    MAIL_LOG_FILE = BASE_DIR / "instance" / "test-mail.log"

    @classmethod
    def validate(cls) -> None:
        validate_mysql_database_url(cls.SQLALCHEMY_DATABASE_URI, "TEST_DATABASE_URL")
