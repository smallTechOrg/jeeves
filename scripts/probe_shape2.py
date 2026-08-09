#!/usr/bin/env python
"""Inspect Mem0 v2 get_all(filters=) + search(filters=) shapes. Dev-only."""
import os, json, shutil, tempfile
from pathlib import Path
from dotenv import dotenv_values
env = dotenv_values(Path("/Users/sai/Workspace/Code/valet/.env"))
os.environ["NVIDIA_API_KEY"] = env["NVIDIA_API_KEY"]
os.environ["OPENAI_API_KEY"] = env["NVIDIA_API_KEY"]
os.environ["OPENAI_BASE_URL"] = env["NVIDIA_BASE_URL"]
workdir = Path(tempfile.mkdtemp(prefix="valet_shape2_"))
config = {
    "version": "v1.1",
    "llm": {"provider":"openai","config":{"model":env["NVIDIA_CHAT_MODEL"],"temperature":0.1,"max_tokens":2000,"openai_base_url":env["NVIDIA_BASE_URL"]}},
    "embedder": {"provider":"openai","config":{"model":env["NVIDIA_EMBED_MODEL"],"openai_base_url":env["NVIDIA_BASE_URL"]}},
    "vector_store": {"provider":"chroma","config":{"collection_name":"valet_shape2","path":str(workdir/"chroma")}},
    "history_db_path": str(workdir/"history.db"),
}
from mem0 import Memory
m = Memory.from_config(config)
m.add("I did 3 workouts this week and my goal is a sub-2h half marathon.", user_id="probe")
print("=== GET_ALL(filters) ===")
ga = m.get_all(filters={"user_id":"probe"})
print(type(ga), json.dumps(ga, indent=2, default=str)[:1500])
print("=== SEARCH(filters) ===")
sr = m.search("how many workouts and what is my goal?", filters={"user_id":"probe"})
print(type(sr), json.dumps(sr, indent=2, default=str)[:1500])
shutil.rmtree(workdir, ignore_errors=True)
