from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def env_value(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _mysql_from_url(database_url: str | None) -> dict[str, str | int]:
    if not database_url:
        return {}
    parsed = urlsplit(database_url)
    if parsed.scheme not in {"mysql", "mysql+pymysql"}:
        raise RuntimeError("DATABASE_URL must use mysql or mysql+pymysql.")
    database = parsed.path.lstrip("/")
    return {
        "MYSQL_HOST": parsed.hostname or "localhost",
        "MYSQL_PORT": parsed.port or 3306,
        "MYSQL_USER": unquote(parsed.username or "root"),
        "MYSQL_PASSWORD": unquote(parsed.password or ""),
        "MYSQL_DATABASE": database,
    }


def _mail_password() -> str | None:
    password = env_value("MAIL_PASSWORD")
    if password and env_value("MAIL_SERVER", "").lower() == "smtp.gmail.com":
        return password.replace(" ", "")
    return password


class Config:
    SECRET_KEY = env_value("SECRET_KEY", "dev-secret-key-change-me")
    DATABASE_URL = env_value("DATABASE_URL")
    _MYSQL = _mysql_from_url(DATABASE_URL)

    MYSQL_HOST = env_value("MYSQL_HOST", _MYSQL.get("MYSQL_HOST", "localhost"))
    MYSQL_PORT = int(env_value("MYSQL_PORT", str(_MYSQL.get("MYSQL_PORT", 3306))))
    MYSQL_USER = env_value("MYSQL_USER", _MYSQL.get("MYSQL_USER", "root"))
    MYSQL_PASSWORD = env_value("MYSQL_PASSWORD", _MYSQL.get("MYSQL_PASSWORD", ""))
    MYSQL_DATABASE = env_value("MYSQL_DATABASE", _MYSQL.get("MYSQL_DATABASE", "sahayogi"))

    MAIL_SERVER = env_value("MAIL_SERVER")
    MAIL_PORT = int(env_value("MAIL_PORT", "587"))
    MAIL_USE_TLS = env_value("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = env_value("MAIL_USERNAME")
    MAIL_PASSWORD = _mail_password()
    MAIL_DEFAULT_SENDER = env_value("MAIL_DEFAULT_SENDER", "noreply@sahayogi.local")
    MAIL_LOG_FILE = BASE_DIR / "instance" / "mail.log"

    UPLOAD_FOLDER = BASE_DIR / "instance" / "uploads"
    LOCKOUT_THRESHOLD = int(env_value("LOCKOUT_THRESHOLD", "3"))
    LOCKOUT_DURATION_MINUTES = int(env_value("LOCKOUT_DURATION_MINUTES", "10"))
    PASSWORD_HASH_METHOD = env_value("PASSWORD_HASH_METHOD", "scrypt")
    PASSWORD_RESET_EXPIRY_SECONDS = int(env_value("PASSWORD_RESET_EXPIRY_SECONDS", "1800"))
    DEFAULT_ADMIN_EMAIL = env_value("DEFAULT_ADMIN_EMAIL", "admin@example.com")
    DEFAULT_ADMIN_PASSWORD = env_value("DEFAULT_ADMIN_PASSWORD", "Admin123!")
    DEFAULT_ADMIN_NAME = env_value("DEFAULT_ADMIN_NAME", "Sahayogi Admin")
    WTF_CSRF_ENABLED = env_value("WTF_CSRF_ENABLED", "true").lower() == "true"

    @classmethod
    def validate(cls) -> None:
        required = {
            "MYSQL_HOST": cls.MYSQL_HOST,
            "MYSQL_USER": cls.MYSQL_USER,
            "MYSQL_DATABASE": cls.MYSQL_DATABASE,
        }
        missing = [name for name, value in required.items() if value in {None, ""}]
        if missing:
            raise RuntimeError(f"Missing MySQL settings: {', '.join(missing)}.")


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    DATABASE_URL = env_value("TEST_DATABASE_URL")
    _MYSQL = _mysql_from_url(DATABASE_URL)
    MYSQL_HOST = env_value("TEST_MYSQL_HOST", _MYSQL.get("MYSQL_HOST", "localhost"))
    MYSQL_PORT = int(env_value("TEST_MYSQL_PORT", str(_MYSQL.get("MYSQL_PORT", 3306))))
    MYSQL_USER = env_value("TEST_MYSQL_USER", _MYSQL.get("MYSQL_USER", "root"))
    MYSQL_PASSWORD = env_value("TEST_MYSQL_PASSWORD", _MYSQL.get("MYSQL_PASSWORD", ""))
    MYSQL_DATABASE = env_value("TEST_MYSQL_DATABASE", _MYSQL.get("MYSQL_DATABASE", "sahayogi_test"))
    MAIL_SERVER = None
    MAIL_LOG_FILE = BASE_DIR / "instance" / "test-mail.log"
