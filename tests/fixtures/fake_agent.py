#!/usr/bin/env python3
"""
tests/fixtures/fake_agent.py - a stand-in for the Kiro resurrector, for tests/test_loop.py.

Called the way the loop calls kiro-cli: `python fake_agent.py <script.json> <prompt>`, with the
repo as the working directory. Each call consumes the next step of the script:
  {"edit": [old, new]}          str_replace in routines/<name>.py
  {"write": text}               create routines/<name>.py
  {"touch": path}               write a file somewhere (to test the guard check)
  {"fail": rc, "stderr": text}  exit with rc and print text to stderr (e.g. a 429)
  {"credits": c}                usage reported in the stream-json (default 0.25)
  {"say": text}                 final message (default "done")
It writes stream-json lines shaped like kiro-cli's and records every prompt it received.
"""
import json
import sys
from pathlib import Path


def main() -> int:
    script_path, prompt = Path(sys.argv[1]), sys.argv[2]
    state = json.loads(script_path.read_text(encoding="utf-8"))
    step = state["steps"][state["next"]] if state["next"] < len(state["steps"]) else {}
    state["next"] += 1
    state.setdefault("prompts", []).append(prompt)
    script_path.write_text(json.dumps(state), encoding="utf-8")

    port = Path("routines") / f"{state['name']}.py"
    if "write" in step:
        port.write_text(step["write"], encoding="utf-8")
    if "edit" in step:
        old, new = step["edit"]
        text = port.read_text(encoding="utf-8")
        port.write_text(text.replace(old, new), encoding="utf-8")
    if "touch" in step:
        Path(step["touch"]).write_text("x", encoding="utf-8")
    usage = {"data": {"update": {"_meta": {"kiro": {"promptTurnSummaries":
                                                    [{"usage": step.get("credits", 0.25)}]}}}}}
    print(json.dumps(usage))
    if "fail" in step:
        print(step.get("stderr", "error"), file=sys.stderr)
        return int(step["fail"])
    print(json.dumps({"data": {"update": {"sessionUpdate": "agent_message_chunk",
                                          "content": {"text": step.get("say", "done")}}}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
