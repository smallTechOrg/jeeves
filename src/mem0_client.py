"""Shared Mem0 Memory instance (semantic layer) for Valet.

Mem0 does semantic recall only — it returns cleaned memory strings, not structured facts.
Valet's own extraction (see extractor.py) produces the structured relational facts that
land in SQLite. Mem0 is used for: (a) durable semantic storage of each message, and
(b) similarity search when answering questions (Phase 2).

NOTE: Mem0's OpenAI-backed LLM/embedder reads the key from the OPENAI_API_KEY / OPENAI_BASE_URL
environment variables at construction time (not purely from the config dict). We export them
from our settings so the same validated credentials are used everywhere. The key value is
never printed or read into logs.
"""
from __future__ import annotations

import os

from mem0 import Memory

from . import config

# Export the OpenAI-compatible credentials Mem0 expects. These mirror NVIDIA's endpoint.
os.environ.setdefault("OPENAI_API_KEY", str(config.NVIDIA_API_KEY))
os.environ.setdefault("OPENAI_BASE_URL", str(config.NVIDIA_BASE_URL))

_MEMORY: Memory | None = None


def get_memory() -> Memory:
    global _MEMORY
    if _MEMORY is None:
        mem0_config = {
            "version": "v1.1",
            "llm": {
                "provider": "openai",
                "config": {
                    "model": config.NVIDIA_CHAT_MODEL,
                    "temperature": 0.1,
                    "max_tokens": 2000,
                    "openai_base_url": config.NVIDIA_BASE_URL,
                },
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": config.NVIDIA_EMBED_MODEL,
                    "openai_base_url": config.NVIDIA_BASE_URL,
                },
            },
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": "valet_memories",
                    "path": str(config.CHROMA_PATH),
                },
            },
            "history_db_path": str(config.REPO_ROOT / "mem0_history.db"),
        }
        _MEMORY = Memory.from_config(mem0_config)
    return _MEMORY
