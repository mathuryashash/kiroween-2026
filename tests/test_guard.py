"""
tests/test_guard.py — pytest gate for tools/guard/allowlist_guard.py

Uses REAL payload shapes from research/15 (probe1/probe2 hook_log.jsonl):
  - tool names: fs_write, fs_append, str_replace, delete_file, execute_pwsh, execute_bash
  - absolute paths arrive with LOWERCASE drive letter and backslashes:
      d:\\hackathons\\kiroween\\repo\\routines\\x.py
  - cwd in payload is similarly formatted

Allowlist = routines/** and .kiro/specs/** only.
Everything else that a write tool touches → exit 2.
Shell tools → always exit 2.
Non-dict tool_input → exit 2 (fail-closed).
"""

import json
import os
import subprocess
import sys

import pytest

# Path to the guard under test
GUARD = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "tools", "guard", "allowlist_guard.py")
)
PYTHON = sys.executable

# Fake workspace root matching real probe payload style (lowercase drive)
WORKSPACE = "d:\\\\hackathons\\\\kiroween\\\\repo"  # double-escaped for JSON strings
# Actual string value (single backslash)
WS = "d:\\hackathons\\kiroween\\repo"


# Tests must never write to the real decision log in runs/.
_ENV = dict(os.environ, GALVANI_GUARD_LOG=os.path.join(
    os.environ.get("TEMP", os.path.dirname(__file__)), "galvani_guard_test_log"))


def _run(payload: dict) -> tuple[int, str]:
    r = subprocess.run(
        [PYTHON, GUARD],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=_ENV,
    )
    return r.returncode, r.stderr.strip()


def _run_raw(raw: str) -> tuple[int, str]:
    r = subprocess.run(
        [PYTHON, GUARD],
        input=raw,
        capture_output=True,
        text=True,
        env=_ENV,
    )
    return r.returncode, r.stderr.strip()


def _p(rel: str) -> str:
    """Build an absolute path under the fake workspace (backslash style like real probes)."""
    return WS + "\\" + rel.replace("/", "\\")


# ---------------------------------------------------------------------------
# ALLOWED cases → exit 0
# ---------------------------------------------------------------------------

def test_allow_routines_relative():
    code, _ = _run({
        "tool_name": "fs_write",
        "tool_input": {"path": "routines/x.py", "text": "pass\n"},
        "cwd": WS,
    })
    assert code == 0


def test_allow_routines_absolute_lowercase_drive():
    """Real probe payload style: absolute path with lowercase d:\\ drive."""
    code, _ = _run({
        "tool_name": "fs_write",
        "tool_input": {"path": _p("routines/x.py"), "text": "pass\n"},
        "cwd": WS,
    })
    assert code == 0


def test_allow_routines_deep():
    code, _ = _run({
        "tool_name": "fs_append",
        "tool_input": {"path": _p("routines/dgamma.py"), "text": "# more\n"},
        "cwd": WS,
    })
    assert code == 0


def test_allow_kiro_specs():
    code, _ = _run({
        "tool_name": "fs_write",
        "tool_input": {"path": ".kiro/specs/dgamma.md", "text": "# spec"},
        "cwd": WS,
    })
    assert code == 0


def test_allow_kiro_specs_absolute():
    code, _ = _run({
        "tool_name": "fs_write",
        "tool_input": {"path": _p(".kiro/specs/dgamma.md"), "text": "# spec"},
        "cwd": WS,
    })
    assert code == 0


def test_allow_read_fortran_source():
    code, _ = _run({
        "tool_name": "read_file",
        "tool_input": {"path": _p("fortran/slatec/dgamma.f"), "offset": None, "limit": None},
        "cwd": WS,
    })
    assert code == 0


def test_block_read_sealed_exam():
    """The exam is sealed: harness, oracle, tests, variants and runs are unreadable."""
    for rel in ["harness/driver.py", "oracle/referees.py", "tests/test_harness.py",
                "fortran/variants/dgamma_fixed.f", "runs/dgamma/latest.json", "harness/README.md"]:
        code, _ = _run({
            "tool_name": "read_file",
            "tool_input": {"path": _p(rel), "offset": None, "limit": None},
            "cwd": WS,
        })
        assert code == 2, rel


def test_block_search_over_workspace_root():
    code, _ = _run({
        "tool_name": "grep_search",
        "tool_input": {"path": WS, "query": "DGAMMA"},
        "cwd": WS,
    })
    assert code == 2


def test_block_read_outside_workspace():
    """Read tools may not leave the workspace (planning notes outside it would leak hints)."""
    code, _ = _run({
        "tool_name": "read_file",
        "tool_input": {"path": "d:\\hackathons\\kiroween\\research\\13_spike_findings.md"},
        "cwd": WS,
    })
    assert code == 2


def test_allow_list_directory():
    """list_directory is read-only → exit 0 regardless of path."""
    code, _ = _run({
        "tool_name": "list_directory",
        "tool_input": {"path": _p("harness"), "depth": None},
        "cwd": WS,
    })
    assert code == 0


def test_allow_no_path_in_input():
    """Write tool with no path field → nothing to check → exit 0."""
    code, _ = _run({
        "tool_name": "fs_write",
        "tool_input": {},
        "cwd": WS,
    })
    assert code == 0


# ---------------------------------------------------------------------------
# BLOCKED write-tool cases → exit 2
# ---------------------------------------------------------------------------

def test_block_harness():
    code, _ = _run({
        "tool_name": "fs_write",
        "tool_input": {"path": _p("harness/driver.py"), "text": "evil"},
        "cwd": WS,
    })
    assert code == 2


def test_block_oracle():
    code, _ = _run({
        "tool_name": "fs_append",
        "tool_input": {"path": _p("oracle/referees.py"), "text": "evil"},
        "cwd": WS,
    })
    assert code == 2


def test_block_tests():
    code, _ = _run({
        "tool_name": "fs_write",
        "tool_input": {"path": _p("tests/test_harness.py"), "text": "evil"},
        "cwd": WS,
    })
    assert code == 2


def test_block_fortran():
    code, _ = _run({
        "tool_name": "fs_write",
        "tool_input": {"path": _p("fortran/slatec/dgamma.f"), "text": "evil"},
        "cwd": WS,
    })
    assert code == 2


def test_block_tools():
    code, _ = _run({
        "tool_name": "fs_write",
        "tool_input": {"path": _p("tools/guard/allowlist_guard.py"), "text": "evil"},
        "cwd": WS,
    })
    assert code == 2


def test_block_runs():
    code, _ = _run({
        "tool_name": "fs_write",
        "tool_input": {"path": _p("runs/dgamma/original_x.json"), "text": "evil"},
        "cwd": WS,
    })
    assert code == 2


def test_block_kiro_steering():
    code, _ = _run({
        "tool_name": "str_replace",
        "tool_input": {"path": _p(".kiro/steering/project-rules.md"), "old_str": "a", "new_str": "b"},
        "cwd": WS,
    })
    assert code == 2


def test_block_kiro_agents():
    code, _ = _run({
        "tool_name": "fs_write",
        "tool_input": {"path": _p(".kiro/agents/resurrector.json"), "text": "evil"},
        "cwd": WS,
    })
    assert code == 2


def test_block_path_traversal():
    """routines/../harness/x.py resolves inside harness/ → blocked."""
    code, _ = _run({
        "tool_name": "fs_write",
        "tool_input": {"path": "routines/../harness/x.py", "text": "evil"},
        "cwd": WS,
    })
    assert code == 2


def test_block_path_outside_workspace():
    """Path on a different drive / entirely outside workspace → blocked."""
    code, _ = _run({
        "tool_name": "fs_write",
        "tool_input": {"path": "c:\\windows\\system32\\hack.py", "text": "evil"},
        "cwd": WS,
    })
    assert code == 2


def test_block_delete_file_harness():
    code, _ = _run({
        "tool_name": "delete_file",
        "tool_input": {"path": _p("harness/trial.py")},
        "cwd": WS,
    })
    assert code == 2


# ---------------------------------------------------------------------------
# Shell tools → always exit 2
# ---------------------------------------------------------------------------

def test_block_execute_pwsh():
    """Real probe2 payload: agent tried Add-Content via execute_pwsh."""
    code, _ = _run({
        "tool_name": "execute_pwsh",
        "tool_input": {
            "command": "Add-Content harness/exam.py '# hacked2'",
            "description": None,
            "cwd": WS,
            "run_in_background": False,
            "timeout": None,
        },
        "cwd": WS,
    })
    assert code == 2


def test_block_execute_bash():
    code, _ = _run({
        "tool_name": "execute_bash",
        "tool_input": {"command": "echo evil >> harness/exam.py"},
        "cwd": WS,
    })
    assert code == 2


# ---------------------------------------------------------------------------
# str_replace operations[] variant
# ---------------------------------------------------------------------------

def test_block_str_replace_operations_array():
    """str_replace with operations[].path pointing at tests/ → blocked."""
    code, _ = _run({
        "tool_name": "str_replace",
        "tool_input": {
            "operations": [
                {"path": _p("tests/test_harness.py"), "old_str": "a", "new_str": "b"}
            ]
        },
        "cwd": WS,
    })
    assert code == 2


def test_allow_str_replace_operations_array_routines():
    """str_replace operations[].path pointing at routines/ → allowed."""
    code, _ = _run({
        "tool_name": "str_replace",
        "tool_input": {
            "operations": [
                {"path": _p("routines/dgamma.py"), "old_str": "a", "new_str": "b"}
            ]
        },
        "cwd": WS,
    })
    assert code == 0


# ---------------------------------------------------------------------------
# Fail-closed cases → exit 2
# ---------------------------------------------------------------------------

def test_parallel_decisions_all_logged(tmp_path):
    """20 guard processes at once must leave 20 log records (first probe lost one)."""
    env = dict(os.environ, GALVANI_GUARD_LOG=str(tmp_path))
    payload = json.dumps({"tool_name": "fs_write",
                          "tool_input": {"path": _p("harness/x.py")}, "cwd": WS})
    procs = [subprocess.Popen([PYTHON, GUARD], stdin=subprocess.PIPE, env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
             for _ in range(20)]
    for p in procs:
        p.communicate(payload)
    assert all(p.returncode == 2 for p in procs)
    assert len(list(tmp_path.glob("*.json"))) == 20


def test_fail_closed_malformed_json():
    code, _ = _run_raw("NOT VALID JSON {{")
    assert code == 2


def test_fail_closed_empty_stdin():
    code, _ = _run_raw("")
    assert code == 2


def test_fail_closed_non_dict_tool_input():
    """Non-dict tool_input → fail-closed → exit 2."""
    code, _ = _run({
        "tool_name": "fs_write",
        "tool_input": "some_string_not_a_dict",
        "cwd": WS,
    })
    assert code == 2
