"""
harness/kiro_session.py - parse Kiro stream-json session logs.

Extracts credits, final agent text, tool calls, and guard denials from a
gzipped or plain .jsonl log produced by `kiro-cli chat --output-format stream-json`.

Usage:
  from harness.kiro_session import parse_session
  info = parse_session("runs/kiro_sessions/dgamma_round1.jsonl.gz")
  print(f"Credits used: {info['credits']}")
  print(f"Agent final text: {info['final_text']}")
"""

import gzip
import json
from pathlib import Path


def parse_session(log_path: str | Path) -> dict:
    """Parse a Kiro stream-json log. Returns parsed metadata.
    
    Returns:
      {
        "credits": float,
        "final_text": str,
        "tool_calls": list[dict],  # {tool, args, result_summary}
        "guard_denials": list[dict],  # {tool, path, reason}
        "error": str | None,  # if the session failed
      }
    """
    log_path = Path(log_path)
    
    credits = 0.0
    final_text_chunks = []
    tool_calls = []
    guard_denials = []
    error = None
    
    opener = gzip.open if log_path.suffix == ".gz" else open
    
    try:
        with opener(log_path, "rt", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as exc:
                    # Partial writes or corrupted logs: skip
                    continue
                
                # Credits
                if "data" in obj and "update" in obj["data"]:
                    upd = obj["data"]["update"]
                    
                    # Prompt turn summaries contain usage
                    meta = upd.get("_meta", {})
                    kiro_meta = meta.get("kiro", {})
                    summaries = kiro_meta.get("promptTurnSummaries", [])
                    for s in summaries:
                        usage = s.get("usage", 0.0)
                        if isinstance(usage, dict):          # tolerate a dict form
                            usage = usage.get("credits", 0.0)
                        try:
                            credits += float(usage or 0.0)
                        except (TypeError, ValueError):
                            pass
                    
                    # Agent message chunks
                    if upd.get("sessionUpdate") == "agent_message_chunk":
                        content = upd.get("content", {})
                        text = content.get("text", "")
                        if text:
                            final_text_chunks.append(text)
                    
                    # Tool calls (best-effort extraction from content blocks)
                    if upd.get("sessionUpdate") == "agent_message_chunk":
                        content = upd.get("content", {})
                        for block in content.get("blocks", []):
                            if block.get("type") == "tool_use":
                                tool_calls.append({
                                    "tool": block.get("name", "?"),
                                    "args": block.get("input", {}),
                                    "id": block.get("id"),
                                })
                    
                    # Tool results
                    if upd.get("sessionUpdate") == "user_message_chunk":
                        content = upd.get("content", {})
                        for block in content.get("blocks", []):
                            if block.get("type") == "tool_result":
                                tid = block.get("tool_use_id")
                                # match to earlier call
                                for tc in tool_calls:
                                    if tc.get("id") == tid:
                                        tc["result_summary"] = str(block.get("content", ""))[:200]
                    
                    # Guard denials (heuristic: look for stderr/output containing "DENY")
                    # Real logs may vary; this is best-effort.
                    if "content" in upd and isinstance(upd["content"], dict):
                        for block in upd["content"].get("blocks", []):
                            if block.get("type") == "tool_result":
                                txt = str(block.get("content", ""))
                                if "DENY" in txt or "denied" in txt.lower():
                                    guard_denials.append({
                                        "tool_use_id": block.get("tool_use_id"),
                                        "content": txt[:300],
                                    })
                
                # Error events
                if "error" in obj:
                    e = obj["error"]
                    error = e.get("message", str(e)) if isinstance(e, dict) else str(e)
    
    except Exception as exc:
        error = f"Failed to parse log: {exc}"
    
    return {
        "credits": round(credits, 4),
        "final_text": "".join(final_text_chunks),
        "tool_calls": tool_calls,
        "guard_denials": guard_denials,
        "error": error,
    }
