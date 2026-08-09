"""Shared Mem0 Memory instance (semantic layer) for Jeeves.

Mem0 does semantic recall only — it returns cleaned memory strings, not structured facts.
Jeeves's own extraction (see extractor.py) produces the structured relational facts that
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
        # Vector store: Supabase (pgvector) in prod when configured, else local Chroma for dev.
        # If a Supabase init fails we fall back to Chroma so the app still boots — only the
        # *semantic* recall layer degrades; relational facts (your durable memory) still land
        # in Supabase Postgres via SQLAlchemy.
        if config.MEM0_USE_SUPABASE:
            vector_store = {
                "provider": "supabase",
                "config": {
                    # mem0 2.x Supabase backend takes ONLY a postgres connection string
                    # (no separate url/key). Requires the `vecs` package.
                    "connection_string": str(config.JEEVES_DB_URL),
                    "collection_name": "jeeves_memories",
                    "embedding_model_dims": 1024,  # nvidia/nemotron-3-embed-1b dimensionality
                },
            }
        else:
            vector_store = {
                "provider": "chroma",
                "config": {
                    "collection_name": "jeeves_memories",
                    "path": str(config.CHROMA_PATH),
                },
            }

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
            "vector_store": vector_store,
            "history_db_path": str(config.REPO_ROOT / "mem0_history.db"),
        }
        try:
            _MEMORY = Memory.from_config(mem0_config)
        except Exception as exc:  # noqa: BLE001 — never let Mem0 config break the whole app
            if config.MEM0_USE_SUPABASE:
                # Supabase vector store failed; degrade to local Chroma for semantic recall.
                print(
                    f"[jeeves] WARNING: Mem0 Supabase init failed ({exc!r}); "
                    "falling back to local Chroma for semantic recall only. "
                    "Relational facts still persist in Supabase Postgres."
                )
                _MEMORY = Memory.from_config({**mem0_config, "vector_store": {
                    "provider": "chroma",
                    "config": {"collection_name": "jeeves_memories", "path": str(config.CHROMA_PATH)},
                }})
            else:
                raise
    return _MEMORY
