"""Seed 10k leads and report read and insert latency.

Run from the repo root:
    python scripts/bench.py
"""

import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import db  # noqa: E402

ROWS = 10_000
READS = 300


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(pct / 100 * len(ordered)) - 1))
    return ordered[index]


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        conn = db.connect(Path(tmp) / "bench.db")
        db.init_db(conn)

        start = time.perf_counter()
        with conn:
            for i in range(ROWS):
                db.upsert_lead(
                    conn,
                    {
                        "external_id": f"bench-{i}",
                        "source": "site" if i % 2 else "partner",
                        "name": f"Lead {i}",
                        "email": f"lead{i}@company.com",
                        "status": "hot" if i % 3 else "new",
                        "score": 80 if i % 3 else 0,
                    },
                )
        insert_seconds = time.perf_counter() - start

        reads: list[float] = []
        for _ in range(READS):
            t0 = time.perf_counter()
            db.list_leads(conn, limit=50)
            reads.append((time.perf_counter() - t0) * 1000)

        filtered: list[float] = []
        for _ in range(READS):
            t0 = time.perf_counter()
            db.list_leads(conn, status="hot", limit=50)
            filtered.append((time.perf_counter() - t0) * 1000)

        print(
            json.dumps(
                {
                    "rows": ROWS,
                    "insert_seconds": round(insert_seconds, 2),
                    "insert_per_row_us": round(insert_seconds / ROWS * 1_000_000, 1),
                    "read_p50_ms": round(statistics.median(reads), 3),
                    "read_p95_ms": round(percentile(reads, 95), 3),
                    "filtered_read_p50_ms": round(statistics.median(filtered), 3),
                    "filtered_read_p95_ms": round(percentile(filtered, 95), 3),
                },
                indent=2,
            )
        )
        conn.close()


if __name__ == "__main__":
    main()
