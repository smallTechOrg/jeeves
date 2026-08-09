#!/usr/bin/env python
"""Probe NVIDIA embedding models via the embeddings endpoint, hard timeout."""
import sys, os, subprocess
from pathlib import Path
from dotenv import dotenv_values

env = dotenv_values(Path("/Users/sai/Workspace/Code/valet/.env"))
os.environ["NVIDIA_API_KEY"] = env["NVIDIA_API_KEY"]
os.environ["NVIDIA_BASE_URL"] = env["NVIDIA_BASE_URL"]
model = sys.argv[1]

code = f'''
import sys, os
from openai import OpenAI
c = OpenAI(api_key=os.environ["NVIDIA_API_KEY"], base_url=os.environ["NVIDIA_BASE_URL"], timeout=20)
try:
    r = c.embeddings.create(model={model!r}, input="hello world")
    print("RESULT OK dims=", len(r.data[0].embedding))
except BaseException as e:
    print("RESULT FAIL", type(e).__name__, str(e)[:180].replace(chr(10)," "))
'''
try:
    subprocess.run([sys.executable, "-c", code], timeout=30, check=False)
except subprocess.TimeoutExpired:
    print("RESULT TIMEOUT")
