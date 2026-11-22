import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def db_path() -> Path:
    return Path(os.getenv("DB_PATH", BASE_DIR / "leads.db"))


def rules_path() -> Path:
    return Path(os.getenv("RULES_PATH", BASE_DIR / "rules.yaml"))
