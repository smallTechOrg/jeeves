"""Valet memory orchestration: capture a message, extract facts, mirror to SQLite, store in Mem0.

This is the core loop. `add_message` is the entry point used by the API.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from . import db, mem0_client, extractor
from .config import USER_ID


def add_message(text: str) -> dict:
    """Process one user message end-to-end.

    Returns a summary dict the API/UI can render:
      { message_id, stored_in_mem0, facts: [ {category, entity, fact_text, confidence, status} ] }
    """
    text = (text or "").strip()
    facts = extractor.extract_facts(text)

    # Mirror structured facts into SQLite (the relational store).
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
        row = db.list_facts()
        # find the just-inserted row by id
        just = next((r for r in row if r["id"] == fid), None)
        if just:
            mirrored.append({
                "id": just["id"],
                "category": just["category"],
                "entity": just["entity"],
                "fact_text": just["fact_text"],
                "confidence": just["confidence"],
                "status": just["status"],
            })

    # Also push the raw message to Mem0 for semantic recall (Phase 2 retrieval).
    mem0_id = None
    stored_in_mem0 = False
    try:
        mem = mem0_client.get_memory()
        result = mem.add(text, user_id=USER_ID)
        results = result.get("results", []) if isinstance(result, dict) else []
        mem0_id = results[0].get("id") if results else None
        stored_in_mem0 = True
    except Exception:
        # Semantic store is best-effort; the relational mirror is the source of truth.
        stored_in_mem0 = False

    return {
        "message_id": mem0_id or f"local-{len(mirrored)}",
        "stored_in_mem0": stored_in_mem0,
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
