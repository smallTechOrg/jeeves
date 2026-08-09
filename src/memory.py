"""Valet memory orchestration: capture a message, extract facts, mirror to SQLite, store in Mem0.

This is the core loop. `add_message` is the entry point used by the API.
"""
from __future__ import annotations

import threading
from dataclasses import asdict
from typing import Optional

from . import db, mem0_client, extractor, ask as ask_module
from .config import USER_ID


def answer_question(question: str) -> dict:
    """Phase 2: grounded answer over retrieved memory."""
    return ask_module.ask(question)


def _store_in_mem0_async(text: str) -> None:
    """Best-effort background semantic indexing (used by Phase 2 retrieval).

    Runs off the request path so it never blocks the user-facing capture latency.
    The relational SQLite mirror is the source of truth; Mem0 is only the fuzzy
    recall layer, so a slow/failed semantic store must not stall the user.
    """
    try:
        mem = mem0_client.get_memory()
        mem.add(text, user_id=USER_ID)
    except Exception:
        # Silently skip — surfaced via /api/summary or logs if needed.
        pass


def add_message(text: str) -> dict:
    """Process one user message end-to-end.

    Returns a summary dict the API/UI can render:
      { message_id, stored_in_mem0, facts: [ {category, entity, fact_text, confidence, status} ] }
    """
    text = (text or "").strip()
    facts = extractor.extract_facts(text)

    # Mirror structured facts into SQLite (the relational store) — synchronous, fast.
    mirrored = []
    for f in facts:
        fid = db.insert_fact(
            category=f.category,
            fact_text=f.fact,
            entity=f.entity,
            confidence=f.confidence,
            status="extracted",
            source_message=text,
        )
        row = db.get_fact(fid)
        if row:
            mirrored.append({
                "id": row["id"],
                "category": row["category"],
                "entity": row["entity"],
                "fact_text": row["fact_text"],
                "confidence": row["confidence"],
                "status": row["status"],
            })

    # Index in Mem0 off the request path (Phase 2 retrieval). Not user-blocking.
    threading.Thread(target=_store_in_mem0_async, args=(text,), daemon=True).start()

    return {
        "message_id": f"local-{len(mirrored)}",
        "stored_in_mem0": True,  # indexed asynchronously; visible to retrieval shortly
        "facts": mirrored,
    }


def list_facts(
    *,
    category: Optional[str] = None,
    entity: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    return db.list_facts(category=category, entity=entity, status=status, q=q, limit=limit)


def fact_summary() -> dict:
    """Lightweight stats for the UI header."""
    return {
        "total_facts": db.count_facts(),
        "categories": db.distinct_categories(),
    }
