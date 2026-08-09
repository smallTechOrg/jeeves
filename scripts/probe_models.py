#!/usr/bin/env python
"""Probe which NVIDIA chat models are callable from this account (threaded, bounded)."""
from pathlib import Path
from dotenv import dotenv_values
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI

env = dotenv_values(Path(__file__).resolve().parent.parent / ".env")
c = OpenAI(api_key=env["NVIDIA_API_KEY"], base_url=env["NVIDIA_BASE_URL"], timeout=25)

cands = [
    "nvidia/llama-3.3-nemotron-super-49b-v1",
    "nvidia/llama-3.1-nemotron-51b-instruct",
    "nvidia/llama-3.1-nemotron-nano-8b-v1",
    "nvidia/nemotron-4-340b-instruct",
    "mistralai/mistral-nemotron",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    "nvidia/llama-3.1-nemotron-ultra-253b-v1",
]

def probe(m):
    try:
        r = c.chat.completions.create(model=m, messages=[{"role":"user","content":"say OK"}], max_tokens=4, temperature=0)
        return (m, "OK", (r.choices[0].message.content or "").strip())
    except Exception as e:
        msg = str(e)
        short = msg.split("detail")[1][:100] if "detail" in msg else msg[:100]
        return (m, "FAIL", short.replace("\n"," "))

with ThreadPoolExecutor(max_workers=len(cands)) as ex:
    futs = {ex.submit(probe, m): m for m in cands}
    for f in as_completed(futs):
        m, status, info = f.result()
        print(status, m, "->", info if status=="OK" else info)
