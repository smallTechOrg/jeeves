"""Jeeves configuration — loads .env, exposes typed settings.

Absolute path to .env is resolved from the repo root so sandboxed runners can't
silently report a missing key (pitfall §16).
"""
from __future__ import annotations
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"

_raw = dotenv_values(ENV_PATH)

# API key must come from the real .env (never committed). If absent we still load
# defaults so the app can boot for non-LLM paths (e.g. reading cached facts offline).
NVIDIA_API_KEY = _raw.get("NVIDIA_API_KEY", "") or os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = _raw.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_CHAT_MODEL = _raw.get("NVIDIA_CHAT_MODEL", "nvidia/nemotron-3-super-120b-a12b")
# Extraction runs on every message. On this NVIDIA account ONLY the 120B reliably extracts
# structured facts (49B/30B models return empty facts — silently losing memory). So
# extraction uses 120B too; Mem0 indexing is backgrounded to keep capture latency low.
NVIDIA_EXTRACT_MODEL = _raw.get("NVIDIA_EXTRACT_MODEL", "nvidia/nemotron-3-super-120b-a12b")
NVIDIA_EMBED_MODEL = _raw.get("NVIDIA_EMBED_MODEL", "nvidia/nemotron-3-embed-1b")

JEEVES_DB_PATH = REPO_ROOT / str(_raw.get("JEEVES_DB_PATH", "./jeeves.db"))
JEEVES_HOST = str(_raw.get("JEEVES_HOST", "127.0.0.1"))
JEEVES_PORT = int(str(_raw.get("JEEVES_PORT", "8000")))

# Time zone the owner lives in. Drives "today"/"now" and date-aware answers so a fact
# captured at 11pm local isn't mislabeled as the next day. IANA name (e.g. "America/New_York").
JEEVES_TZ = _raw.get("JEEVES_TZ", "") or os.environ.get("JEEVES_TZ", "") or "UTC"
try:
    LOCAL_TZ = ZoneInfo(JEEVES_TZ)
except Exception:
    LOCAL_TZ = ZoneInfo("UTC")  # invalid tz name -> fall back safely


def local_now():
    """Current time in the owner's time zone (tz-aware datetime)."""
    return datetime.now(LOCAL_TZ)

# Mem0's local Chroma store lives next to the DB.
CHROMA_PATH = REPO_ROOT / "chroma_store"
CHROMA_PATH.mkdir(parents=True, exist_ok=True)

# Single fixed user for the personal-agent use case (Phase 1).
USER_ID = "owner"

# Extraction categories are dynamic (LLM-invented), but we keep a known seed list so the
# UI has sensible defaults to group by. New categories are accepted on the fly.
SEED_CATEGORIES = [
    "Identity", "Goal", "Plan", "Workout", "Nutrition", "Health",
    "Preference", "Relationship", "Work", "Finance", "Learning", "Event",
    "Mood", "Feeling",
]
