"""FastAPI application for Jeeves (Phase 1: capture + query)."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import memory
from . import db
from .schemas import MessageIn, MessageOut, AskIn, FactEditIn, ChatIn

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = REPO_ROOT / "static"

app = FastAPI(title="Jeeves", version="0.1.0")


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


@app.post("/api/ask")
def post_ask(payload: AskIn):
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    return memory.answer_question(question)


@app.post("/api/chat")
def post_chat(payload: ChatIn):
    """Unified inbox: classify intent (fact / question / vent) and route accordingly."""
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    return memory.route_message(text)


@app.get("/api/summary")
def get_summary():
    return memory.fact_summary()


@app.post("/api/facts/{fact_id}/verify")
def post_verify(fact_id: int):
    ok = memory.verify_fact(fact_id)
    if not ok:
        raise HTTPException(status_code=404, detail="fact not found")
    return {"ok": True, "id": fact_id, "status": "verified"}


@app.patch("/api/facts/{fact_id}")
def patch_fact(fact_id: int, payload: FactEditIn):
    ok = memory.edit_fact(
        fact_id,
        fact_text=payload.fact_text,
        category=payload.category,
        entity=payload.entity,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="fact not found")
    return {"ok": True, "id": fact_id}


# Serve the SPA at /
@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


# Mount static assets (app.js, style.css)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
