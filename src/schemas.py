"""Pydantic API schemas for Valet."""
from __future__ import annotations

from pydantic import BaseModel


class MessageIn(BaseModel):
    text: str


class FactOut(BaseModel):
    id: int
    category: str
    entity: str | None = None
    fact_text: str
    confidence: float
    status: str


class MessageOut(BaseModel):
    message_id: str
    stored_in_mem0: bool
    facts: list[dict]


class AskIn(BaseModel):
    question: str
