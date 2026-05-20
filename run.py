from __future__ import annotations

import os
import sys
from importlib.util import find_spec
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
VENV_PYTHON = BASE_DIR / "venv" / "Scripts" / "python.exe"
REQUIRED_MODULES = {
    "flask": "Flask",
    "flask_login": "Flask-Login",
    "pymysql": "PyMySQL",
    "dotenv": "python-dotenv",
    "cryptography": "cryptography",
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

    print_startup_error(f"Missing Python packages: {', '.join(missing)}.")
    print("\nInstall them with:")
    print("  py setup.py")
    print("\nIf setup was already run, use the project virtual environment:")
    print(r"  .\venv\Scripts\python.exe run.py")
    sys.exit(1)


restart_with_venv_python()
verify_python_dependencies()

import pymysql

from app import create_app
from app.database import Database


try:
    app = create_app()
except RuntimeError as exc:
    print_startup_error(str(exc))
    sys.exit(1)


def verify_database_connection() -> None:
    try:
        with app.app_context():
            db = Database()
            try:
                db.fetch_one("SELECT 1 AS ok")
                if not db.fetch_one("SHOW TABLES LIKE 'roles'"):
                    print_startup_error(
                        "MySQL is reachable, but the Sahayogi tables are missing. "
                        "Run the init and seed commands for this database."
                    )
                    sys.exit(1)
            finally:
                db.close()
    except pymysql.MySQLError as exc:
        print_startup_error(
            "MySQL rejected the configured settings. "
            "This usually means .env has the wrong password, the database was not created, "
            "or the MySQL service is not running."
        )
        print(f"\nDatabase error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    verify_database_connection()
    port = int(os.getenv("PORT", "5000"))
    app.run(debug=True, port=port)
