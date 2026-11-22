import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.main import create_app  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    app = create_app(tmp_path / "test.db", ROOT / "rules.yaml")
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def lead():
    return {
        "external_id": "amo-1042",
        "source": "site",
        "name": "Ilyas",
        "email": "i@company.com",
    }
