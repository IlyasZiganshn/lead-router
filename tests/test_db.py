import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import db  # noqa: E402


def test_unique_index_survives_two_connections(tmp_path):
    path = tmp_path / "two.db"
    first = db.connect(path)
    db.init_db(first)
    second = db.connect(path)
    data = {"external_id": "x1", "source": "site", "name": "A", "email": "a@company.com"}
    with first:
        _, created_first = db.upsert_lead(first, data)
    with second:
        _, created_second = db.upsert_lead(second, data)
    assert created_first is True
    assert created_second is False
    assert db.stats(first)["total"] == 1
    first.close()
    second.close()


def test_failed_transaction_leaves_no_rows(tmp_path):
    path = tmp_path / "tx.db"
    conn = db.connect(path)
    db.init_db(conn)
    try:
        with conn:
            db.upsert_lead(
                conn,
                {"external_id": "x1", "source": "site", "email": "a@company.com"},
            )
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert db.stats(conn)["total"] == 0
    conn.close()
