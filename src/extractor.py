"""Structured fact extraction — turns one user message into relational facts.

Single LLM call per message (never per-line — pitfall §7). Output is strict JSON so it
parses deterministically into SQLite rows. Categories are LLM-invented (dynamic), seeded
with known ones for grouping. Beyond a textual fact, each fact carries DERIVED attributes
(quantity, unit, period, date) so memory becomes genuinely relational/queryable.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Optional

from openai import OpenAI

from . import config

_SYSTEM = (
    "You are the memory extractor for 'Valet', a personal agent that stores factual, "
    "structured memory about its owner. Given a short message from the owner, extract "
    "discrete, self-contained FACTS. For each fact provide:\n"
    "- category: a short noun describing the type of fact. Prefer one of: "
    + ", ".join(config.SEED_CATEGORIES)
    + ". Invent a NEW concise category only if none fit (e.g. 'Travel', 'Hobby').\n"
    "- entity: the specific subject the fact is about (a person, goal, activity, thing), "
    "or null if not applicable.\n"
    "- fact: a clean, atomic, factual statement in third person about the owner, suitable "
    "to store verbatim as a memory (e.g. 'Owner completed 3 workouts this week').\n"
    "- confidence: a number 0.0-1.0 estimating how certain the statement is and how "
    "literally factual (1.0 = explicit statement, lower if vague/hedged).\n"
    "- quantity: the numeric amount in the fact if it has one (e.g. 3 for '3 workouts'), "
    "else null.\n"
    "- unit: the unit of that quantity (e.g. 'workouts', 'km', 'hours', 'pages'), else null.\n"
    "- period: the time window the fact refers to (e.g. 'this week', 'today', '2026-08', "
    "'weekend'), else null.\n"
    "- fact_date: the ISO date (YYYY-MM-DD) the fact is about if clearly stated or "
    "impliable from 'today/yesterday', else null.\n"
    "Return ONLY a JSON object: {\"facts\": [ {category, entity, fact, confidence, "
    "quantity, unit, period, fact_date}, ... ]}. "
    "If the message contains no extractable facts, return {\"facts\": []}. "
    "Do not wrap in markdown. No commentary."
)


@dataclass
class ExtractedFact:
    category: str
    fact: str
    entity: Optional[str] = None
    confidence: float = 0.5
    quantity: Optional[float] = None
    unit: Optional[str] = None
    period: Optional[str] = None
    fact_date: Optional[str] = None

    def to_row(self) -> dict:
        d = asdict(self)
        return d


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        return f if f == f else None  # guard NaN
    except (TypeError, ValueError):
        return None


def _to_str(v) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def extract_facts(message: str) -> list[ExtractedFact]:
    if not config.NVIDIA_API_KEY:
        # Offline mode: store the raw message as a single uncategorized fact so the
        # pipeline still works without a key (e.g. demoing the UI). Marked low confidence.
        return [ExtractedFact(category="Uncategorized", fact=message.strip(), confidence=0.0)]

    client = OpenAI(api_key=config.NVIDIA_API_KEY, base_url=config.NVIDIA_BASE_URL, timeout=60)
    resp = client.chat.completions.create(
        model=str(config.NVIDIA_EXTRACT_MODEL),
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": message},
        ],
        temperature=0.0,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
        raw = data.get("facts", [])
    except json.JSONDecodeError:
        raw = []

    facts: list[ExtractedFact] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        fact_text = (item.get("fact") or "").strip()
        if not fact_text:
            continue
        cat = (item.get("category") or "Uncategorized").strip() or "Uncategorized"
        ent = _to_str(item.get("entity"))
        try:
            conf = float(item.get("confidence", 0.5))
        except (TypeError, ValueError):
            conf = 0.5
        conf = max(0.0, min(1.0, conf))
        facts.append(ExtractedFact(
            category=cat,
            fact=fact_text,
            entity=ent,
            confidence=conf,
            quantity=_to_float(item.get("quantity")),
            unit=_to_str(item.get("unit")),
            period=_to_str(item.get("period")),
            fact_date=_to_str(item.get("fact_date")),
        ))
    return facts
