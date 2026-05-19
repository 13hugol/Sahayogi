#!/usr/bin/env python
"""
Sahayogi Setup Script
Run this on a fresh machine to configure MySQL and seed the database.

Usage:
    python setup.py
"""
from __future__ import annotations

import os
import getpass
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote_plus


BASE_DIR = Path(__file__).resolve().parent
VENV_DIR = BASE_DIR / "venv"
PYTHON = str(VENV_DIR / "Scripts" / "python.exe")
FLASK = str(VENV_DIR / "Scripts" / "flask.exe")
MYSQL_CLIENT_PATHS = [
    r"C:\Program Files\MySQL\MySQL Server 9.6\bin\mysql.exe",
    r"C:\Program Files\MySQL\MySQL Server 9.5\bin\mysql.exe",
    r"C:\Program Files\MySQL\MySQL Server 9.4\bin\mysql.exe",
    r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
]


def find_mysql_client() -> str | None:
    for path in MYSQL_CLIENT_PATHS:
        if Path(path).exists():
            return path
    # Try to find in PATH
    result = subprocess.run(["where", "mysql"], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip().split("\n")[0]
    return None


def print_header(text: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")


def print_success(text: str) -> None:
    print(f"  [OK] {text}")


def print_error(text: str) -> None:
    print(f"  [FAIL] {text}")


def run_cmd(
    cmd: list[str],
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=cwd or str(BASE_DIR),
        capture_output=True,
        text=True,
        env=env,
    )


def check_mysql() -> str:
    """Check if MySQL is installed and running. Returns path to mysql.exe."""
    mysql_client = find_mysql_client()
    if not mysql_client:
        print_error("MySQL client not found. Please install MySQL Server.")
        sys.exit(1)

    # Check service name from installed services
    result = run_cmd(["sc", "query"])
    mysql_service = None
    for line in result.stdout.split("\n"):
        if "MySQL" in line and "SERVICE_NAME" in line:
            mysql_service = line.split(":")[-1].strip()
            break

    if mysql_service:
        status_result = run_cmd(["sc", "query", mysql_service])
        if "RUNNING" not in status_result.stdout:
            print_error(f"MySQL service ({mysql_service}) is not running. Start it and try again.")
            sys.exit(1)
    else:
        print("  Warning: Could not find MySQL service. Assuming it's running.")

    print_success(f"MySQL found at: {mysql_client}")
    return mysql_client


def get_root_password() -> str:
    """Prompt for MySQL root password."""

    password = os.getenv("MYSQL_ROOT_PASSWORD")
    if password:
        return password

    print("\nEnter your MySQL root password:")
    print("  Note: typed characters are hidden. Type the password and press Enter.")
    try:
        password = getpass.getpass("  Password: ")
    except (EOFError, getpass.GetPassWarning):
        print("  Hidden password input is not available in this terminal.")
        password = input("  Password (visible): ")

    if not password:
        print_error("Password cannot be empty. Exiting.")
        print("  You can also run: $env:MYSQL_ROOT_PASSWORD='your-password'; py setup.py")
        sys.exit(1)
    return password


def prompt_hidden(label: str) -> str:
    import getpass

    try:
        return getpass.getpass(label)
    except (EOFError, getpass.GetPassWarning):
        print("  Hidden input is not available in this terminal.")
        return input(label.replace("(hidden)", "(visible)"))


def get_mail_settings() -> dict[str, str]:
    print("\nEmail setup:")
    print("  Press Enter to skip SMTP and log emails to instance/mail.log.")
    configure = input("  Configure Gmail SMTP now? [y/N]: ").strip().lower()
    if configure not in {"y", "yes"}:
        return {
            "MAIL_SERVER": "",
            "MAIL_USERNAME": "",
            "MAIL_PASSWORD": "",
            "MAIL_DEFAULT_SENDER": "noreply@sahayogi.local",
        }

    email = input("  Gmail address: ").strip()
    password = prompt_hidden("  Gmail App Password (hidden): ").replace(" ", "")
    if not email or not password:
        print("  Gmail settings incomplete. Emails will be logged locally.")
        return {
            "MAIL_SERVER": "",
            "MAIL_USERNAME": "",
            "MAIL_PASSWORD": "",
            "MAIL_DEFAULT_SENDER": "noreply@sahayogi.local",
        }

    return {
        "MAIL_SERVER": "smtp.gmail.com",
        "MAIL_USERNAME": email,
        "MAIL_PASSWORD": password,
        "MAIL_DEFAULT_SENDER": email,
    }


def test_mysql_connection(mysql_client: str, password: str) -> bool:
    """Test MySQL connection with the provided password."""
    result = run_cmd([mysql_client, "-u", "root", f"-p{password}", "-e", "SELECT 1;"])
    if result.returncode != 0:
        print_error("Connection failed. Check your password and try again.")
        print(f"  Error: {result.stderr.strip()}")
        return False
    print_success("MySQL connection successful")
    return True


def create_database(mysql_client: str, password: str) -> bool:
    """Create the application and test databases."""
    result = run_cmd([
        mysql_client, "-u", "root", f"-p{password}",
        "-e",
        (
            "CREATE DATABASE IF NOT EXISTS sahayogi CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            "CREATE DATABASE IF NOT EXISTS sahayogi_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        ),
    ])
    if result.returncode != 0:
        print_error("Failed to create databases")
        print(f"  Error: {result.stderr.strip()}")
        return False
    print_success("Databases 'sahayogi' and 'sahayogi_test' created")
    return True


def create_venv() -> bool:
    """Create virtual environment if it doesn't exist."""
    if VENV_DIR.exists():
        print_success("Virtual environment already exists")
        return True

    print("  Creating virtual environment...")
    result = run_cmd([sys.executable, "-m", "venv", str(VENV_DIR)])
    if result.returncode != 0:
        print_error("Failed to create virtual environment")
        return False
    print_success("Virtual environment created")
    return True


def install_dependencies() -> bool:
    """Install Python dependencies."""
    print("  Installing dependencies...")
    result = run_cmd([PYTHON, "-m", "pip", "install", "-r", "requirements.txt", "--quiet"])
    if result.returncode != 0:
        print_error("Failed to install dependencies")
        print(f"  Error: {result.stderr.strip()}")
        return False
    print_success("Dependencies installed")
    return True


def generate_env(password: str, mail_settings: dict[str, str] | None = None) -> None:
    """Generate .env file with MySQL and mail settings."""
    encoded_password = quote_plus(password)
    mail_settings = mail_settings or {
        "MAIL_SERVER": "",
        "MAIL_USERNAME": "",
        "MAIL_PASSWORD": "",
        "MAIL_DEFAULT_SENDER": "noreply@sahayogi.local",
    }
    env_content = f"""SECRET_KEY=change-me
DATABASE_URL=mysql+pymysql://root:{encoded_password}@localhost:3306/sahayogi
TEST_DATABASE_URL=mysql+pymysql://root:{encoded_password}@localhost:3306/sahayogi_test
MAIL_SERVER={mail_settings['MAIL_SERVER']}
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME={mail_settings['MAIL_USERNAME']}
MAIL_PASSWORD={mail_settings['MAIL_PASSWORD']}
MAIL_DEFAULT_SENDER={mail_settings['MAIL_DEFAULT_SENDER']}
DEFAULT_ADMIN_EMAIL=admin@example.com
DEFAULT_ADMIN_PASSWORD=Admin123!
DEFAULT_ADMIN_NAME=Sahayogi Admin
INITIAL_CREDITS=10
"""
    env_path = BASE_DIR / ".env"
    env_path.write_text(env_content, encoding="utf-8")
    print_success(".env file generated")
    if mail_settings["MAIL_SERVER"]:
        print("  Gmail SMTP configured. Run: flask test-email your-email@gmail.com")
    else:
        print("  Note: Emails are logged to instance/mail.log until Gmail SMTP is configured.")


def run_migrations() -> bool:
    """Run Flask database migrations."""
    print("  Running database migrations...")
    env = os.environ.copy()
    env["FLASK_APP"] = "run.py"
    result = run_cmd([PYTHON, "-m", "flask", "db", "upgrade"], cwd=str(BASE_DIR), env=env)
    if result.returncode != 0:
        print_error("Failed to run migrations")
        print(f"  Error: {result.stderr.strip()}")
        return False
    print_success("Database migrations applied")
    return True


def seed_reference_data() -> bool:
    """Seed reference data (roles, categories, skills, admin)."""
    print("  Seeding reference data...")
    env = os.environ.copy()
    env["FLASK_APP"] = "run.py"
    result = run_cmd([PYTHON, "-m", "flask", "seed-reference-data"], cwd=str(BASE_DIR), env=env)
    if result.returncode != 0:
        print_error("Failed to seed reference data")
        print(f"  Error: {result.stderr.strip()}")
        return False
    print_success("Reference data seeded")
    return True


def seed_demo_data() -> bool:
    """Seed demo users, listings, and exchanges."""
    print("  Seeding demo data...")
    env = os.environ.copy()
    env["FLASK_APP"] = "run.py"
    result = run_cmd([PYTHON, "-m", "flask", "seed-demo-data"], cwd=str(BASE_DIR), env=env)
    if result.returncode != 0:
        print_error("Failed to seed demo data")
        print(f"  Error: {result.stderr.strip()}")
        return False
    print_success("Demo data seeded")
    return True


def print_demo_credentials() -> None:
    """Print demo user credentials."""
    print_header("Setup Complete!")
    print("Demo Users (password: Demo1234!):")
    print("  anisha@demo.local  - Python, Flask, SQL")
    print("  rajesh@demo.local  - Graphic Design, Photography")
    print("  sunita@demo.local  - Marketing, Public Speaking")
    print("  bikash@demo.local  - English, Nepali Basics")
    print()
    print("Admin:")
    print("  admin@example.com  - Admin123!")
    print()
    print("Start the server with: py run.py")
    print("Then visit: http://localhost:5000")


def main() -> None:
    print_header("Sahayogi Setup")

    mysql_client = check_mysql()

    password = get_root_password()

    if not test_mysql_connection(mysql_client, password):
        sys.exit(1)

    if not create_database(mysql_client, password):
        sys.exit(1)

    if not create_venv():
        sys.exit(1)

    if not install_dependencies():
        sys.exit(1)

    mail_settings = get_mail_settings()
    generate_env(password, mail_settings)

    if not run_migrations():
        sys.exit(1)

    if not seed_reference_data():
        sys.exit(1)

    if not seed_demo_data():
        sys.exit(1)

    print_demo_credentials()


if __name__ == "__main__":
    main()
