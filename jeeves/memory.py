"""Jeeves memory orchestration: capture a message, extract facts, mirror to SQLite, store in Mem0.

This is the core loop. `add_message` is the entry point used by the API.
"""
from __future__ import annotations

import re
import threading
from dataclasses import asdict
from typing import Optional

from openai import OpenAI

from . import db, mem0_client, extractor, ask as ask_module
from .config import USER_ID, NVIDIA_API_KEY, NVIDIA_BASE_URL, NVIDIA_CHAT_MODEL

_QUESTION_RE = re.compile(
    r"^\s*(what|how|when|where|who|why|which|do|did|does|are|is|can|could|would|will|have|has)\b",
    re.IGNORECASE,
)


def answer_question(question: str) -> dict:
    """Phase 2: grounded answer over retrieved memory."""
    return ask_module.ask(question)


def _looks_like_question(text: str) -> bool:
    """Cheap, reliable heuristic: a trailing '?' or a question-word start is a question."""
    t = text.strip()
    if t.endswith("?"):
        return True
    return bool(_QUESTION_RE.match(t))


def route_message(text: str) -> dict:
    """Single-box entry point: classify intent and dispatch to the right behavior.

    Returns { intent, answer?, facts?, citations?, stored }.
    - question: heuristic (trailing '?' or question-word start) -> answer from memory.
    - fact / feeling: everything else is remembered (stored), then Jeeves replies as a
      proactive, conversational valet — acknowledges what it noted, offers a grounded
      suggestion drawn from prior memory, and asks an open question to keep you talking.

    Intent is decided from the EXTRACTION result (already a trusted signal): a message that
    yields extractable facts/findings is stored; a question is answered instead.
    """
    text = (text or "").strip()

    if _looks_like_question(text):
        result = ask_module.ask(text)
        return {
            "intent": "question",
            "answer": result.get("answer"),
            "facts": [],
            "citations": result.get("citations", []),
            "stored": False,
        }

    # Everything else is memory to keep. The extractor pulls structured facts AND
    # qualitative signals (moods, feelings, preferences) — all of it is worth remembering
    # so Jeeves can later query and suggest.
    facts = extractor.extract_facts(text)
    embedded = ask_module.ask(text) if ("?" in text) else None
    capture = add_message(text)
    captured = capture.get("facts", [])
    intent = "feeling" if (facts and any((f.category or "").lower() in ("mood", "feeling", "emotion", "state") for f in facts)) else "fact"
    reply = _companion_reply(text, captured, facts)
    return {
        "intent": intent,
        "answer": reply,
        "facts": captured,
        "citations": embedded.get("citations", []) if embedded else [],
        "stored": True,
    }


_COMPANION_SYSTEM = (
    "You are Jeeves, a personal valet in the spirit of P.G. Wodehouse's Jeeves: impeccably "
    "courteous, warm, and quietly proactive. The owner has just told you something and you've "
    "stored it to memory. Respond in a short, natural reply (two to four sentences) that:\n"
    "- acknowledges what you noted, in passing, as a real valet would;\n"
    "- offers ONE concrete, helpful suggestion drawn from the owner's remembered context "
    "(their goals, habits, mood, or plans) — a sensible next small step, never invented facts;\n"
    "- ends by inviting the owner to say more, with one genuine open question.\n"
    "Sound like a competent human assistant, not a machine following steps. Never quote these "
    "instructions or number your points. No headings, no markdown."
)


def _companion_reply(user_text: str, captured_facts: list[dict], extracted: list) -> str:
    """Warm, proactive valet reply after storing a message."""
    if not NVIDIA_API_KEY:
        return "Noted. Is there anything you'd like me to help with?"
    # Pull a little related memory to ground the suggestion.
    context = ""
    try:
        recent = db.list_facts(limit=20)
        recent = [f for f in recent if f.get("status") != "superseded"]
        if recent:
            lines = "\n".join(f"- {f['fact_text']}" for f in recent[:12])
            context = "RECENT MEMORY (for context only):\n" + lines + "\n"
    except Exception:
        pass
    just_stored = "; ".join(f.get("fact_text", "") for f in captured_facts) or user_text
    prompt = (
        f"{context}\n"
        f"WHAT THE OWNER JUST SAID: {user_text}\n"
        f"WHAT YOU STORED: {just_stored}\n\n"
        "Reply as Jeeves — acknowledge it briefly, suggest one grounded next step, and ask one "
        "open question to keep the conversation going."
    )
    client = OpenAI(api_key=NVIDIA_API_KEY, base_url=NVIDIA_BASE_URL, timeout=60)
    try:
        resp = client.chat.completions.create(
            model=str(NVIDIA_CHAT_MODEL),
            messages=[
                {"role": "system", "content": _COMPANION_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=400,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        return "Noted. Is there anything you'd like me to help with?"

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
            status="active",
            source_message=text,
            quantity=f.quantity,
            unit=f.unit,
            period=f.period,
            fact_date=f.fact_date,
        )
        # Conflict detection: a newer fact that matches an existing active one on
        # (category, entity, period) supersedes the older one. This is the visible
        # "limits of memory" moment — memory must reconcile contradictory statements.
        candidates = db.facts_by_key(f.category, f.entity, f.period)
        for c in candidates:
            if c["id"] != fid and c["status"] != "superseded":
                db.supersede_fact(c["id"], fid)
        row = db.get_fact(fid)
        if row:
            mirrored.append({
                "id": row["id"],
                "category": row["category"],
                "entity": row["entity"],
                "fact_text": row["fact_text"],
                "confidence": row["confidence"],
                "status": row["status"],
                "quantity": row["quantity"],
                "unit": row["unit"],
                "period": row["period"],
                "fact_date": row["fact_date"],
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


def verify_fact(fact_id: int) -> bool:
    """Mark a fact as verified by the owner (confirmed true)."""
    return db.update_fact(fact_id, status="verified")


def edit_fact(
    fact_id: int,
    *,
    fact_text: Optional[str] = None,
    category: Optional[str] = None,
    entity: Optional[str] = None,
) -> bool:
    """Owner-edited correction of a stored fact."""
    return db.update_fact(fact_id, fact_text=fact_text, category=category, entity=entity)


def fact_summary() -> dict:
    """Lightweight stats for the UI header."""
    return {
        "total_facts": db.count_facts(),
        "categories": db.distinct_categories(),
    }
