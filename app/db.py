import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"


def utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def connect(path: str | Path) -> sqlite3.Connection:
    # One connection per request. FastAPI may create the dependency in a worker
    # thread and run an async endpoint on the event loop thread, so the default
    # same-thread check is too strict for this usage.
    conn = sqlite3.connect(str(path), timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def lead_to_dict(row: sqlite3.Row) -> dict:
    lead = dict(row)
    lead["payload"] = json.loads(lead.get("payload") or "{}")
    return lead


def upsert_lead(conn: sqlite3.Connection, data: dict) -> tuple[dict, bool]:
    now = utcnow()
    cur = conn.execute(
        """
        INSERT INTO leads
            (external_id, source, name, email, status, score, payload, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(external_id) DO NOTHING
        """,
        (
            data["external_id"],
            data["source"],
            data.get("name"),
            data.get("email"),
            data.get("status", "new"),
            int(data.get("score", 0)),
            json.dumps(data.get("payload") or {}, ensure_ascii=False),
            now,
            now,
        ),
    )
    created = cur.rowcount == 1
    row = conn.execute(
        "SELECT * FROM leads WHERE external_id = ?", (data["external_id"],)
    ).fetchone()
    if created:
        insert_event(conn, row["id"], "created", {"source": row["source"]})
    return lead_to_dict(row), created


def insert_event(conn: sqlite3.Connection, lead_id: int, kind: str, payload: dict) -> None:
    conn.execute(
        "INSERT INTO events (lead_id, kind, payload, created_at) VALUES (?, ?, ?, ?)",
        (lead_id, kind, json.dumps(payload, ensure_ascii=False), utcnow()),
    )


def get_lead(conn: sqlite3.Connection, lead_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    return lead_to_dict(row) if row else None


def get_lead_by_external_id(conn: sqlite3.Connection, external_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM leads WHERE external_id = ?", (external_id,)).fetchone()
    return lead_to_dict(row) if row else None


def list_leads(
    conn: sqlite3.Connection,
    status: str | None = None,
    source: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    sql = "SELECT * FROM leads WHERE 1 = 1"
    params: list = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if source:
        sql += " AND source = ?"
        params.append(source)
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(sql, params).fetchall()
    return [lead_to_dict(row) for row in rows]


def update_status(conn: sqlite3.Connection, lead_id: int, status: str) -> dict | None:
    row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if row is None:
        return None
    previous = row["status"]
    conn.execute(
        "UPDATE leads SET status = ?, updated_at = ? WHERE id = ?",
        (status, utcnow(), lead_id),
    )
    insert_event(conn, lead_id, "status_changed", {"from": previous, "to": status})
    return get_lead(conn, lead_id)


def stats(conn: sqlite3.Connection) -> dict:
    by_source = {
        row["source"]: row["count"]
        for row in conn.execute(
            "SELECT source, COUNT(*) AS count FROM leads GROUP BY source ORDER BY source"
        ).fetchall()
    }
    by_status = {
        row["status"]: row["count"]
        for row in conn.execute(
            "SELECT status, COUNT(*) AS count FROM leads GROUP BY status ORDER BY status"
        ).fetchall()
    }
    total = conn.execute("SELECT COUNT(*) AS count FROM leads").fetchone()["count"]
    return {"total": total, "by_source": by_source, "by_status": by_status}
