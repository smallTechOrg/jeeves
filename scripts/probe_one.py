#!/usr/bin/env python
"""Probe a single NVIDIA model slug with a hard process-level timeout."""
import argparse, subprocess, sys, os
from pathlib import Path
from dotenv import dotenv_values

env = dotenv_values(Path("/Users/sai/Workspace/Code/valet/.env"))
os.environ["NVIDIA_API_KEY"] = env["NVIDIA_API_KEY"]
os.environ["NVIDIA_BASE_URL"] = env["NVIDIA_BASE_URL"]

parser = argparse.ArgumentParser()
parser.add_argument("model")
args = parser.parse_args()

code = f'''
import sys, os
from openai import OpenAI
c = OpenAI(api_key=os.environ["NVIDIA_API_KEY"], base_url=os.environ["NVIDIA_BASE_URL"], timeout=20)
try:
    r = c.chat.completions.create(model={args.model!r}, messages=[{{"role":"user","content":"say OK"}}], max_tokens=4, temperature=0)
    print("RESULT OK", (r.choices[0].message.content or "").strip())
except BaseException as e:
    print("RESULT FAIL", type(e).__name__, str(e)[:180].replace(chr(10)," "))
'''
try:
    subprocess.run([sys.executable, "-c", code], timeout=30, check=False)
except subprocess.TimeoutExpired:
    print("RESULT TIMEOUT")
