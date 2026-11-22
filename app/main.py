import csv
import io
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import (
    Body,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from pydantic import BaseModel, Field

from app import db
from app.config import db_path, rules_path
from app.rules import ALLOWED_STATUSES, apply_rules, load_rules


class LeadIn(BaseModel):
    external_id: str = Field(min_length=1, max_length=128)
    source: str = Field(min_length=1, max_length=64)
    name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=200)
    payload: dict = Field(default_factory=dict)


def valid_email(value: str | None) -> bool:
    if value is None:
        return True
    if value.count("@") != 1:
        return False
    local, domain = value.split("@")
    return bool(local) and "." in domain and not domain.startswith(".") and not domain.endswith(".")


def get_conn(request: Request):
    conn = db.connect(request.app.state.db_path)
    try:
        yield conn
    finally:
        conn.close()


def parse_csv(raw: bytes) -> list[dict]:
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "external_id" not in reader.fieldnames:
        raise ValueError("CSV must contain an external_id column")
    return [dict(row) for row in reader]


def create_app(database: str | Path | None = None, rules_file: str | Path | None = None) -> FastAPI:
    db_file = Path(database) if database else db_path()
    rules = load_rules(rules_file or rules_path())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        conn = db.connect(db_file)
        db.init_db(conn)
        conn.close()
        yield

    app = FastAPI(title="lead-router", version="0.1.0", lifespan=lifespan)
    app.state.db_path = db_file
    app.state.rules = rules

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/leads")
    def create_lead(
        payload: LeadIn,
        response: Response,
        conn=Depends(get_conn),
    ) -> dict:
        if not valid_email(payload.email):
            raise HTTPException(status_code=422, detail="invalid email")
        data = payload.model_dump()
        score, status, rule = apply_rules(data, app.state.rules)
        data["score"] = score
        data["status"] = status
        with conn:
            lead, created = db.upsert_lead(conn, data)
        response.status_code = 201 if created else 200
        return {"lead": lead, "duplicate": not created, "rule": rule}

    @app.get("/leads")
    def list_leads(
        status: str | None = Query(default=None),
        source: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        conn=Depends(get_conn),
    ) -> dict:
        items = db.list_leads(conn, status, source, limit, offset)
        return {"items": items, "count": len(items), "limit": limit, "offset": offset}

    @app.get("/leads/{lead_id}")
    def get_lead(lead_id: int, conn=Depends(get_conn)) -> dict:
        lead = db.get_lead(conn, lead_id)
        if lead is None:
            raise HTTPException(status_code=404, detail="lead not found")
        return lead

    @app.patch("/leads/{lead_id}")
    def patch_lead(
        lead_id: int,
        status: str = Body(embed=True),
        conn=Depends(get_conn),
    ) -> dict:
        if status not in ALLOWED_STATUSES:
            allowed = sorted(ALLOWED_STATUSES)
            raise HTTPException(status_code=422, detail=f"status must be one of {allowed}")
        with conn:
            lead = db.update_status(conn, lead_id, status)
        if lead is None:
            raise HTTPException(status_code=404, detail="lead not found")
        return lead

    @app.post("/import")
    async def import_csv(file: UploadFile = File(...), conn=Depends(get_conn)) -> dict:
        raw = await file.read()
        try:
            rows = parse_csv(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        created = duplicates = invalid = 0
        errors: list[str] = []
        with conn:
            for index, row in enumerate(rows, start=2):
                external_id = (row.get("external_id") or "").strip()
                source = (row.get("source") or "").strip()
                email = (row.get("email") or "").strip() or None
                if not external_id or not source or not valid_email(email):
                    invalid += 1
                    if len(errors) < 10:
                        errors.append(f"line {index}: missing external_id or source, or bad email")
                    continue
                data = {
                    "external_id": external_id,
                    "source": source,
                    "name": (row.get("name") or "").strip() or None,
                    "email": email,
                    "payload": {},
                }
                score, status, _ = apply_rules(data, app.state.rules)
                data["score"] = score
                data["status"] = status
                _, was_created = db.upsert_lead(conn, data)
                if was_created:
                    created += 1
                else:
                    duplicates += 1
        return {
            "rows": len(rows),
            "created": created,
            "duplicates": duplicates,
            "invalid": invalid,
            "errors": errors,
        }

    @app.get("/stats")
    def get_stats(conn=Depends(get_conn)) -> dict:
        return db.stats(conn)

    return app


app = create_app()
