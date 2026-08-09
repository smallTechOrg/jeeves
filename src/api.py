"""FastAPI application for Valet (Phase 1: capture + query)."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import memory
from . import db
from .schemas import MessageIn, MessageOut

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = REPO_ROOT / "static"

app = FastAPI(title="Valet", version="0.1.0")


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


@app.get("/health")
def health():
    return {"status": "ok", "facts": db.count_facts()}


@app.post("/api/message", response_model=MessageOut)
def post_message(payload: MessageIn):
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    result = memory.add_message(text)
    return MessageOut(**result)


@app.get("/api/facts")
def get_facts(
    category: str | None = Query(None),
    entity: str | None = Query(None),
    status: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
):
    return memory.list_facts(category=category, entity=entity, status=status, q=q, limit=limit)


@app.get("/api/summary")
def get_summary():
    return memory.fact_summary()


# Serve the SPA at /
@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


# Mount static assets (app.js, style.css)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
