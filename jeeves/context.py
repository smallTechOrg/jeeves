"""Rolling conversation-context tracking for Jeeves.

The single-box chat is otherwise stateless: each /api/chat call has no memory of what
the owner and Jeeves were just discussing. This module keeps a per-session buffer of
recent turns and periodically condenses them into a short "topic" summary so Jeeves can
stay on-thread (e.g. answer "what about tomorrow?" in the context of the workout plan
that was just mentioned).

Design:
- In-memory dict keyed by session_id (one owner, multiple browser sessions / devices).
- Each turn appends (role, text). Buffer capped at MAX_TURNS.
- A lightweight LLM summary is refreshed every SUMMARY_EVERY turns; if the LLM is
  unavailable it falls back to the last few raw turns so context still works offline.
"""
from __future__ import annotations

import threading
from typing import Optional

from .config import NVIDIA_API_KEY, NVIDIA_BASE_URL, NVIDIA_CHAT_MODEL
from openai import OpenAI

MAX_TURNS = 12          # rolling window kept in full
SUMMARY_EVERY = 4       # re-summarize after this many new turns
_SUMMARY_MAX = 240      # chars cap on the condensed topic string

_lock = threading.Lock()
_sessions: dict[str, dict] = {}


def _new_session(session_id: str) -> dict:
    return {
        "turns": [],          # list of {"role": "user"|"jeeves", "text": str}
        "topic": "",          # condensed current-topic string
        "since_summary": 0,   # turns added since last summary
    }


def get_session(session_id: str) -> dict:
    with _lock:
        return _sessions.setdefault(session_id, _new_session(session_id))


def append_turn(session_id: str, role: str, text: str) -> None:
    """Record a turn and refresh the topic summary when due."""
    sess = get_session(session_id)
    with _lock:
        sess["turns"].append({"role": role, "text": text})
        # cap buffer
        if len(sess["turns"]) > MAX_TURNS:
            sess["turns"] = sess["turns"][-MAX_TURNS:]
        sess["since_summary"] += 1
        due = sess["since_summary"] >= SUMMARY_EVERY
    if due:
        _refresh_summary(session_id)


def get_context(session_id: str) -> str:
    """Return a context string for the LLM (topic summary + recent raw turns)."""
    sess = get_session(session_id)
    with _lock:
        turns = list(sess["turns"])
        topic = sess["topic"]
    if not turns:
        return ""
    lines = [f"- {t['role']}: {t['text']}" for t in turns[-6:]]
    raw = "\n".join(lines)
    if topic:
        return f"CURRENT TOPIC: {topic}\nRECENT EXCHANGE:\n{raw}"
    return f"RECENT EXCHANGE:\n{raw}"


def get_topic(session_id: str) -> str:
    with _lock:
        return _sessions.get(session_id, {}).get("topic", "")


def reset_session(session_id: str) -> None:
    with _lock:
        _sessions[session_id] = _new_session(session_id)


def _refresh_summary(session_id: str) -> None:
    """Condense recent turns into a one-line topic. Best-effort; never raises."""
    sess = get_session(session_id)
    with _lock:
        turns = list(sess["turns"][-6:])
    if not turns:
        return
    transcript = "\n".join(f"{t['role']}: {t['text']}" for t in turns)
    if not NVIDIA_API_KEY:
        # Offline fallback: just keep the last user line as the topic.
        last_user = next((t["text"] for t in reversed(turns) if t["role"] == "user"), "")
        with _lock:
            sess["topic"] = (last_user[:_SUMMARY_MAX] or sess["topic"])
            sess["since_summary"] = 0
        return
    try:
        client = OpenAI(api_key=NVIDIA_API_KEY, base_url=NVIDIA_BASE_URL, timeout=30)
        resp = client.chat.completions.create(
            model=str(NVIDIA_CHAT_MODEL),
            messages=[
                {"role": "system", "content":
                    "Summarize what the owner and Jeeves are currently discussing in ONE short "
                    "phrase (under 20 words). No preamble. Examples: 'planning a half-marathon "
                    "training schedule', 'deciding dinner plans', 'reviewing weekly workouts'."},
                {"role": "user", "content": transcript},
            ],
            temperature=0.2,
            max_tokens=60,
        )
        summary = (resp.choices[0].message.content or "").strip()
        summary = summary[:_SUMMARY_MAX]
        if summary:
            with _lock:
                sess["topic"] = summary
                sess["since_summary"] = 0
    except Exception:
        # Leave the previous topic; don't churn on transient LLM errors.
        with _lock:
            sess["since_summary"] = 0
