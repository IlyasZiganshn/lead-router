"""Seed 10k leads three times and report insert and read latency.

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
RUNS = 3


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(pct / 100 * len(ordered)) - 1))
    return ordered[index]


def run_once() -> dict:
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

        result = {
            "insert_seconds": insert_seconds,
            "read_p50_ms": statistics.median(reads),
            "read_p95_ms": percentile(reads, 95),
            "filtered_read_p50_ms": statistics.median(filtered),
            "filtered_read_p95_ms": percentile(filtered, 95),
        }
        conn.close()
        return result


def summarize_runs(runs: list[dict]) -> dict:
    def median(key: str) -> float:
        return statistics.median(run[key] for run in runs)

    def low(key: str) -> float:
        return min(run[key] for run in runs)

    def high(key: str) -> float:
        return max(run[key] for run in runs)

    return {
        "rows": ROWS,
        "runs": len(runs),
        "insert_seconds_median": round(median("insert_seconds"), 2),
        "insert_seconds_min": round(low("insert_seconds"), 2),
        "insert_seconds_max": round(high("insert_seconds"), 2),
        "insert_per_row_us_median": round(median("insert_seconds") / ROWS * 1_000_000, 1),
        "read_p50_ms_median": round(median("read_p50_ms"), 3),
        "read_p95_ms_median": round(median("read_p95_ms"), 3),
        "read_p95_ms_min": round(low("read_p95_ms"), 3),
        "read_p95_ms_max": round(high("read_p95_ms"), 3),
        "filtered_read_p50_ms_median": round(median("filtered_read_p50_ms"), 3),
        "filtered_read_p95_ms_median": round(median("filtered_read_p95_ms"), 3),
        "filtered_read_p95_ms_min": round(low("filtered_read_p95_ms"), 3),
        "filtered_read_p95_ms_max": round(high("filtered_read_p95_ms"), 3),
    }


def main() -> None:
    runs = [run_once() for _ in range(RUNS)]
    print(json.dumps(summarize_runs(runs), indent=2))


if __name__ == "__main__":
    main()
