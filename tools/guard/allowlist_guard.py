#!/usr/bin/env python3
"""
allowlist_guard.py — PreToolUse allowlist guard for GALVANI resurrector agent.

Reads Kiro PreToolUse STDIN JSON.  Paths arrive as absolute Windows paths with
a lowercase drive letter and backslashes (e.g. d:\\hackathons\\...\\routines\\x.py)
as confirmed by probe1/probe2 hook_log.jsonl.

ALLOWLIST (write destinations):
  routines/**
  .kiro/specs/**

EXIT CODES (Kiro 1.4.154 — only exit 2 blocks a PreToolUse):
  0 = allow
  2 = BLOCK  (stderr is forwarded to the agent as the reason)
  (never exit 1 — silent failure, does NOT block)

Fail-closed: every unexpected exception → exit 2.
"""

import sys
import json
import os
import re

# ---------------------------------------------------------------------------
# Tool classification
# ---------------------------------------------------------------------------

# Shell tools: always blocked.  The resurrector has no shell; trials go
# through the MCP run_trial tool.
SHELL_TOOLS = {"execute_pwsh", "execute_bash"}

# Explicit write tools whose paths we check against the allowlist.
EXPLICIT_WRITE_TOOLS = {"fs_write", "fs_append", "str_replace", "delete_file"}

# Pattern that flags other tool names as likely-write.
_WRITE_NAME_RE = re.compile(
    r"write|append|create|delete|modify|edit|update|rename|move|patch|replace|remove",
    re.IGNORECASE,
)

# Known read-only tools: skip path checking entirely → exit 0.
READ_ONLY_TOOLS = {
    "read_file", "list_directory", "read", "search_files",
    "grep_search", "find_file", "find",
}

# Content the resurrector may read (relative to the workspace root).
READ_ALLOW = (
    "fortran/slatec/", "fortran/support/", "routines/", ".kiro/specs/",
    ".kiro/steering/", "README.md", "LICENSE",
)
LISTING_TOOLS = {"list_directory"}


def _is_read_allowed(rel: str) -> bool:
    for a in READ_ALLOW:
        if a.endswith("/"):
            if rel.startswith(a) or rel == a.rstrip("/"):
                return True
        elif rel == a:
            return True
    return False


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _norm(path: str) -> str:
    """
    Normalise a path to: forward slashes, lowercase drive letter, resolved dots.
    Returns the canonical absolute path string (no trailing slash).
    """
    if not path:
        return ""
    # os.path.normpath handles ../ and .\ on Windows
    p = os.path.normpath(path)
    # Forward slashes everywhere
    p = p.replace("\\", "/")
    # Lowercase drive letter  (e.g.  D:/...  →  d:/...)
    if len(p) >= 2 and p[1] == ":" and p[0].isalpha():
        p = p[0].lower() + p[1:]
    return p


def _resolve(path: str, cwd: str) -> str:
    """
    Resolve *path* relative to *cwd* (if not absolute), then normalise.
    Both inputs should be raw strings as received from the payload.
    """
    if not os.path.isabs(path):
        path = os.path.join(cwd, path)
    return _norm(path)


def _workspace_root(cwd: str) -> str:
    """Return the normalised workspace root (= cwd from payload)."""
    return _norm(cwd)


def _strip_prefix(path: str, prefix: str) -> str | None:
    """
    If *path* starts with *prefix* (case-sensitive after normalisation),
    return the remaining relative part (no leading slash).  Else None.
    """
    prefix = prefix.rstrip("/") + "/"
    if path.startswith(prefix):
        return path[len(prefix):]
    # Also handle exact match (edge case: path == prefix root without trailing /)
    if path == prefix.rstrip("/"):
        return ""
    return None


def _is_in_allowlist(rel: str) -> bool:
    """
    *rel* is the path relative to the workspace root (forward slashes,
    no leading slash).  Returns True iff it falls under routines/ or .kiro/specs/.
    """
    if rel.startswith("routines/") or rel == "routines":
        return True
    if rel.startswith(".kiro/specs/") or rel == ".kiro/specs":
        return True
    return False


# ---------------------------------------------------------------------------
# Path extraction
# ---------------------------------------------------------------------------

def _collect_paths(tool_input: dict) -> list[str]:
    """Extract every file path from a (confirmed-dict) tool_input."""
    paths: list[str] = []
    if "path" in tool_input and isinstance(tool_input["path"], str):
        paths.append(tool_input["path"])
    if "operations" in tool_input and isinstance(tool_input["operations"], list):
        for op in tool_input["operations"]:
            if isinstance(op, dict) and "path" in op and isinstance(op["path"], str):
                paths.append(op["path"])
    return paths


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _log(entry: dict) -> None:
    """Append one JSON line to runs/guard_log.jsonl (best effort; never raises)."""
    try:
        log_path = os.environ.get("GALVANI_GUARD_LOG") or os.path.join(
            os.path.dirname(__file__), "..", "..", "runs", "guard_log.jsonl"
        )
        log_path = os.path.normpath(log_path)
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            raise ValueError("empty stdin")
        data = json.loads(raw)

        tool_name: str = data.get("tool_name", "")
        tool_input = data.get("tool_input")
        cwd: str = data.get("cwd", os.getcwd())

        # --- fail-closed: tool_input must be a dict ---
        if not isinstance(tool_input, dict):
            msg = (
                f"ALLOWLIST GUARD: tool_input is not a dict "
                f"(got {type(tool_input).__name__}) — blocked (fail-closed)."
            )
            print(msg, file=sys.stderr)
            _log({"decision": "block", "reason": "non-dict tool_input", "tool": tool_name})
            sys.exit(2)

        # --- shell tools: always block ---
        if tool_name in SHELL_TOOLS:
            msg = (
                f"ALLOWLIST GUARD: '{tool_name}' is blocked. "
                f"The resurrector has no shell; use the run_trial MCP tool for trials."
            )
            print(msg, file=sys.stderr)
            _log({"decision": "block", "reason": "shell tool", "tool": tool_name})
            sys.exit(2)

        # --- read-only tools: the exam is sealed ---
        # Directory listings may see the whole workspace (names only); reading or
        # searching file CONTENT is limited to READ_ALLOW, so the agent never sees
        # the harness, referee, tests, variants or earlier run results.
        if tool_name in READ_ONLY_TOOLS:
            ws = _workspace_root(cwd)
            for raw_path in _collect_paths(tool_input):
                rel = _strip_prefix(_resolve(raw_path, cwd), ws)
                if rel is None:
                    reason = "read outside workspace"
                elif tool_name in LISTING_TOOLS or _is_read_allowed(rel):
                    continue
                else:
                    reason = "read outside sealed-exam allowlist"
                print(
                    f"ALLOWLIST GUARD: '{tool_name}' on '{raw_path}' blocked ({reason}). "
                    f"Readable: {', '.join(READ_ALLOW)}.",
                    file=sys.stderr,
                )
                _log({"decision": "block", "reason": reason, "tool": tool_name, "path": raw_path})
                sys.exit(2)
            _log({"decision": "allow", "reason": "read-only tool", "tool": tool_name})
            sys.exit(0)

        # --- classify as write? ---
        is_write = (
            tool_name in EXPLICIT_WRITE_TOOLS
            or bool(_WRITE_NAME_RE.search(tool_name))
        )

        # --- collect paths ---
        paths = _collect_paths(tool_input)

        if not paths:
            # No path to check; allow (nothing to protect against)
            _log({"decision": "allow", "reason": "no paths in input", "tool": tool_name})
            sys.exit(0)

        # --- for write tools (or unknown tools with paths), check allowlist ---
        ws = _workspace_root(cwd)

        for raw_path in paths:
            resolved = _resolve(raw_path, cwd)

            # 1. Must be inside workspace
            rel = _strip_prefix(resolved, ws)
            if rel is None:
                msg = (
                    f"ALLOWLIST GUARD: path '{raw_path}' is outside the workspace "
                    f"(workspace={ws}) — blocked."
                )
                print(msg, file=sys.stderr)
                _log({
                    "decision": "block",
                    "reason": "outside workspace",
                    "tool": tool_name,
                    "path": raw_path,
                })
                sys.exit(2)

            # 2. For write tools: must be under routines/ or .kiro/specs/
            if is_write and not _is_in_allowlist(rel):
                msg = (
                    f"ALLOWLIST GUARD: '{tool_name}' on '{raw_path}' is outside the "
                    f"write allowlist (routines/** or .kiro/specs/**) — blocked.\n"
                    f"  resolved={resolved}  rel={rel}"
                )
                print(msg, file=sys.stderr)
                _log({
                    "decision": "block",
                    "reason": "not in write allowlist",
                    "tool": tool_name,
                    "path": raw_path,
                    "rel": rel,
                })
                sys.exit(2)

            # 3. Unknown (non-write) tool with path: check allowlist too
            if not is_write and not _is_in_allowlist(rel):
                # Unknown tool accessing a path outside allowlist → block
                msg = (
                    f"ALLOWLIST GUARD: unknown tool '{tool_name}' on "
                    f"'{raw_path}' (outside allowlist, rel={rel}) — blocked."
                )
                print(msg, file=sys.stderr)
                _log({
                    "decision": "block",
                    "reason": "unknown tool outside allowlist",
                    "tool": tool_name,
                    "path": raw_path,
                    "rel": rel,
                })
                sys.exit(2)

        # All paths passed
        _log({"decision": "allow", "tool": tool_name, "paths": paths})
        sys.exit(0)

    except SystemExit:
        raise
    except Exception as exc:
        print(
            f"ALLOWLIST GUARD ERROR (fail-closed): {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        _log({"decision": "block", "reason": f"exception: {exc}"})
        sys.exit(2)


if __name__ == "__main__":
    main()
