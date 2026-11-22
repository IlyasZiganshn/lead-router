import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent


def db_path() -> Path:
    """The database lives next to the working directory by default."""
    return Path(os.getenv("DB_PATH", "leads.db"))


def rules_path() -> Path:
    """The default rules ship inside the package, so installs work from any directory."""
    return Path(os.getenv("RULES_PATH", PACKAGE_DIR / "rules.yaml"))
