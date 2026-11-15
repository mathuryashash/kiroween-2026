"""PostFileSave hook (non-blocking): record which file the agent saved.

Kiro passes the hook context as JSON on stdin (KIRO_FILE_PATH was empty in practice),
so read the path from there. One file per event under runs/guard_log/ (git-ignored),
same as the guard. Never fails the save.
"""
import json
import os
import sys
import time
import uuid

try:
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except ValueError:
        data = {"raw": raw[:500]}
    path = (os.environ.get("KIRO_FILE_PATH") or data.get("file_path") or data.get("path")
            or (data.get("tool_input") or {}).get("path") or "")
    d = os.environ.get("GALVANI_GUARD_LOG") or os.path.join(os.path.dirname(__file__), "..", "..", "runs", "guard_log")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"{time.time_ns()}_{os.getpid()}_{uuid.uuid4().hex[:6]}_save.json"), "x",
              encoding="utf-8") as fh:
        json.dump({"t": time.time(), "ev": "PostFileSave", "file": path,
                   "keys": sorted(data)[:20] if isinstance(data, dict) else []}, fh)
except Exception:
    pass
sys.exit(0)
