from __future__ import annotations

import os
import sys
from importlib.util import find_spec
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
VENV_PYTHON = BASE_DIR / "venv" / "Scripts" / "python.exe"
REQUIRED_MODULES = {
    "flask": "Flask",
    "flask_bcrypt": "Flask-Bcrypt",
    "flask_login": "Flask-Login",
    "flask_migrate": "Flask-Migrate",
    "flask_sqlalchemy": "Flask-SQLAlchemy",
    "flask_wtf": "Flask-WTF",
    "pymysql": "PyMySQL",
    "dotenv": "python-dotenv",
    "email_validator": "email-validator",
    "cryptography": "cryptography",
    "sqlalchemy": "SQLAlchemy",
}


def print_startup_error(message: str) -> None:
    print("\nSahayogi could not start.")
    print(message)
    print("\nFix:")
    print("  1. Run: py setup.py")
    print("  2. Then start with: py run.py")
    print("  3. Make sure MySQL is installed and running.")


def restart_with_venv_python() -> None:
    if os.environ.get("SAHAYOGI_SKIP_VENV_REEXEC") == "1":
        return
    if not VENV_PYTHON.exists():
        return

    current_python = Path(sys.executable).resolve()
    if current_python == VENV_PYTHON.resolve():
        return

    os.environ["SAHAYOGI_SKIP_VENV_REEXEC"] = "1"
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])


def verify_python_dependencies() -> None:
    missing = [
        package_name
        for module_name, package_name in REQUIRED_MODULES.items()
        if find_spec(module_name) is None
    ]
    if not missing:
        return

    packages = ", ".join(missing)
    print_startup_error(f"Missing Python packages: {packages}.")
    print("\nInstall them with:")
    print("  py setup.py")
    print("\nIf setup was already run, use the project virtual environment:")
    print(r"  .\venv\Scripts\python.exe run.py")
    sys.exit(1)


restart_with_venv_python()
verify_python_dependencies()

from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app import create_app
from app.extensions import db


try:
    app = create_app()
except RuntimeError as exc:
    print_startup_error(str(exc))
    sys.exit(1)


def verify_database_connection() -> None:
    try:
        with app.app_context():
            db.session.execute(text("SELECT 1"))
            if not inspect(db.engine).has_table("role"):
                print_startup_error(
                    "MySQL is reachable, but the Sahayogi tables are missing. "
                    "The database has not been migrated on this device yet."
                )
                sys.exit(1)
            db.session.remove()
    except OperationalError as exc:
        print_startup_error(
            "MySQL rejected the configured DATABASE_URL. "
            "This usually means .env has the wrong root password for this device, "
            "the database was not created, or the MySQL service is not running."
        )
        print(f"\nDatabase error: {exc.orig}")
        sys.exit(1)
    except SQLAlchemyError as exc:
        print_startup_error("Database startup check failed.")
        print(f"\nDatabase error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    verify_database_connection()
    app.run(debug=True)
