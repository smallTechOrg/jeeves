#!/usr/bin/env python
"""
Make-or-break architecture probe: does Mem0 (v2) work with:
  - NVIDIA OpenAI-compatible chat+embed (validated slugs)
  - Chroma as the local vector store (LMDB, file-backed)
  - a real add() + search() round-trip
Prints only status tokens, never secrets.
"""
import os, sys, shutil, tempfile
from pathlib import Path
from dotenv import dotenv_values

env = dotenv_values(Path("/Users/sai/Workspace/Code/valet/.env"))
os.environ["NVIDIA_API_KEY"] = env["NVIDIA_API_KEY"]
os.environ["OPENAI_API_KEY"] = env["NVIDIA_API_KEY"]  # mem0 uses openai provider
os.environ["OPENAI_BASE_URL"] = env["NVIDIA_BASE_URL"]

workdir = Path(tempfile.mkdtemp(prefix="valet_probe_"))
chroma_path = workdir / "chroma"

config = {
    "version": "v1.1",
    "llm": {
        "provider": "openai",
        "config": {
            "model": env["NVIDIA_CHAT_MODEL"],
            "temperature": 0.1,
            "max_tokens": 2000,
            "openai_base_url": env["NVIDIA_BASE_URL"],
        },
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "model": env["NVIDIA_EMBED_MODEL"],
            "openai_base_url": env["NVIDIA_BASE_URL"],
        },
    },
    "vector_store": {
        "provider": "chroma",
        "config": {"collection_name": "valet_probe", "path": str(chroma_path)},
    },
    "history_db_path": str(workdir / "history.db"),
}

try:
    from mem0 import Memory
    m = Memory.from_config(config)
    # Real extraction round-trip
    m.add("I did 3 workouts this week and I'm training for a half marathon. My goal is to run it under 2 hours.",
          user_id="probe")
    res = m.search("how many workouts did I do and what is my running goal?",
                   filters={"user_id": "probe"})
    n = len(res.get("results", []))
    if n > 0:
        print(f"MEM0_OK results={n} chroma_dir={chroma_path.exists()}")
    else:
        print("MEM0_EMPTY no results returned")
except BaseException as e:
    print("MEM0_FAIL", type(e).__name__, str(e)[:200].replace("\n", " "))
finally:
    shutil.rmtree(workdir, ignore_errors=True)
