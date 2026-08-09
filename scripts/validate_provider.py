#!/usr/bin/env python
"""
Valet provider check — validates the NVIDIA (OpenAI-compatible) key AND model slug
with one minimal real call. Prints ONLY a status token, never the key or raw errors.
Run: .venv/bin/python scripts/validate_provider.py
"""
from pathlib import Path
from dotenv import dotenv_values
import os
import sys

# Resolve repo root (this script lives at <repo>/scripts/validate_provider.py)
REPO_ROOT = Path(__file__).resolve().parent.parent
env = dotenv_values(REPO_ROOT / ".env")

KEY = env.get("NVIDIA_API_KEY", "")
BASE = env.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
MODEL = env.get("NVIDIA_CHAT_MODEL", "nvidia/llama-3.1-nemotron-70b-instruct")

if not KEY or KEY.startswith("sk-REPLACE") or KEY == "sk-...":
    print("MISSING")
    sys.exit(1)

try:
    from openai import OpenAI

    client = OpenAI(api_key=KEY, base_url=BASE)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "Reply with the single word: OK"}],
        max_tokens=8,
        temperature=0,
    )
    text = (resp.choices[0].message.content or "").strip().upper()
    if "OK" in text:
        print("OK")
    else:
        print(f"UNEXPECTED:{text[:20]}")
except Exception as e:
    err = type(e).__name__
    msg = str(e)
    if "401" in msg or "auth" in msg.lower() or "invalid" in msg.lower():
        print("401")
    elif "429" in msg or "rate" in msg.lower() or "quota" in msg.lower():
        print("429")
    elif "model" in msg.lower() and ("not" in msg.lower() or "found" in msg.lower()):
        print("model_not_found")
    else:
        print(f"ERROR:{err}")
