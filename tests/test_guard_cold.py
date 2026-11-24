"""
tests/test_guard_cold.py: cold mode of tools/guard/allowlist_guard.py (loop-frozen-2).

Why: in the DLNGAM run of 24 Nov 2026 the agent read the already-healed routines/dgamma.py
(tool call 18 of 22) and pasted it in, so the "heal" was a copy (runs/ledger/
dlngam_20261124T034238Z.NOTE.md). In cold mode the agent may touch only its own port.

The payload shapes are the ones in that session log: read_file / list_directory with
{"path": ...}, fs_write with {"path", "text"}, str_replace with {"path", ...}.
"""

import json
import os
import subprocess
import sys

import pytest

GUARD = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "tools", "guard", "allowlist_guard.py"))
WS = "d:\\hackathons\\kiroween\\repo"


def _p(rel: str) -> str:
    return WS + "\\" + rel.replace("/", "\\")


def _run(payload: dict, state_dir, cold: str | None) -> int:
    env = dict(os.environ, GALVANI_GUARD_LOG=str(state_dir / "log"), GALVANI_GUARD_STATE=str(state_dir))
    marker = state_dir / "cold.json"
    if cold is None:
        marker.unlink(missing_ok=True)
    else:
        marker.write_text(json.dumps({"target": cold}), encoding="utf-8")
    r = subprocess.run([sys.executable, GUARD], input=json.dumps(payload), capture_output=True,
                       text=True, env=env)
    return r.returncode


def _read(rel):
    return {"tool_name": "read_file", "tool_input": {"path": _p(rel), "offset": None, "limit": None},
            "cwd": WS}


def _write(rel):
    return {"tool_name": "fs_write", "tool_input": {"path": _p(rel), "text": "x"}, "cwd": WS}


# --- the exact leak: reading another, already-healed port --------------------------------

def test_cold_blocks_reading_healed_dgamma(tmp_path):
    assert _run(_read("routines/dgamma.py"), tmp_path, cold="dgamr") == 2


def test_warm_still_allows_reading_other_ports(tmp_path):
    """Without the marker nothing changes (loop-frozen-1 behaviour)."""
    assert _run(_read("routines/dgamma.py"), tmp_path, cold=None) == 0


@pytest.mark.parametrize("rel", ["routines/dpsi.py", "routines/dcot.py", "routines/dlngam.py",
                                 "routines/_slatec_common.py", "routines/__init__.py",
                                 ".kiro/specs/cold-heal-remaining-flaws/tasks.md",
                                 ".kiro/specs/cold-heal-remaining-flaws/design.md"])
def test_cold_blocks_other_ports_and_specs(tmp_path, rel):
    assert _run(_read(rel), tmp_path, cold="dgamr") == 2


def test_cold_blocks_grep_over_routines_folder(tmp_path):
    p = {"tool_name": "grep_search", "tool_input": {"path": _p("routines"), "query": "x + (i - 1)"},
         "cwd": WS}
    assert _run(p, tmp_path, cold="dgamr") == 2


def test_cold_blocks_writing_another_port(tmp_path):
    assert _run(_write("routines/dgamma.py"), tmp_path, cold="dgamr") == 2


def test_cold_blocks_writing_specs(tmp_path):
    assert _run(_write(".kiro/specs/cold-heal-remaining-flaws/upstream/dgamr.md"), tmp_path,
                cold="dgamr") == 2


def test_cold_blocks_pathless_code_tool(tmp_path):
    """'code' (code intelligence) came with no path in an earlier session; it could return any file."""
    p = {"tool_name": "code", "tool_input": {"operation": "search_symbols", "symbol_name": "dgamma"},
         "cwd": WS}
    assert _run(p, tmp_path, cold="dgamr") == 2


def test_blocks_pathless_content_search(tmp_path):
    p = {"tool_name": "grep_search", "tool_input": {"query": "x + (i - 1)"}, "cwd": WS}
    assert _run(p, tmp_path, cold="dgamr") == 2
    assert _run(p, tmp_path, cold=None) == 2


# --- what the cold port still needs ------------------------------------------------------

@pytest.mark.parametrize("rel", ["fortran/slatec/dgamr.f", "fortran/slatec/dgamma.f",
                                 "fortran/support/d1mach.f", ".kiro/steering/fortran_translation.md",
                                 "routines/dgamr.py"])
def test_cold_allows_sources_steering_and_own_port(tmp_path, rel):
    assert _run(_read(rel), tmp_path, cold="dgamr") == 0


def test_cold_allows_writing_own_port(tmp_path):
    assert _run(_write("routines/dgamr.py"), tmp_path, cold="dgamr") == 0


def test_cold_allows_str_replace_on_own_port(tmp_path):
    p = {"tool_name": "str_replace", "tool_input": {"path": _p("routines/dgamr.py"),
                                                    "oldStr": "a", "newStr": "b"}, "cwd": WS}
    assert _run(p, tmp_path, cold="dgamr") == 0


def test_cold_allows_listing_routines(tmp_path):
    p = {"tool_name": "list_directory", "tool_input": {"path": _p("routines"), "depth": None}, "cwd": WS}
    assert _run(p, tmp_path, cold="dgamr") == 0


def test_cold_allows_file_name_search(tmp_path):
    p = {"tool_name": "file_search", "tool_input": {"query": "dgamr.f"}, "cwd": WS}
    assert _run(p, tmp_path, cold="dgamr") == 0


# --- fail-closed --------------------------------------------------------------------------

@pytest.mark.parametrize("body", ['{"target": "../harness"}', "not json", '{"nope": 1}'])
def test_bad_marker_blocks_everything(tmp_path, body):
    (tmp_path / "cold.json").write_text(body, encoding="utf-8")
    env = dict(os.environ, GALVANI_GUARD_LOG=str(tmp_path / "log"), GALVANI_GUARD_STATE=str(tmp_path))
    r = subprocess.run([sys.executable, GUARD], input=json.dumps(_read("fortran/slatec/dgamr.f")),
                       capture_output=True, text=True, env=env)
    assert r.returncode == 2
