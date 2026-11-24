"""
tests/test_loop_cold.py: the loop sets the cold-mode marker only while the agent runs.

Uses a fake agent command (python -c ...) that records whether runs/guard_state/cold.json existed
and what it said, so no Kiro credits are spent.
"""

import json
import sys

import harness.loop as L


def _fake_cmd(out_file):
    code = ("import json,os,sys; m=os.path.join('runs','guard_state','cold.json'); "
            f"open(r'{out_file}','w').write(json.dumps(open(m).read() if os.path.exists(m) else None)); "
            "print(json.dumps({'type':'runFinished','data':{'finalText':'done','sessionId':'fake'}}))")
    return [sys.executable, "-c", code]


def test_marker_present_during_call_and_removed_after(tmp_path, monkeypatch):
    seen = tmp_path / "seen.json"
    monkeypatch.setattr(L, "_agent_argv", lambda template, model: _fake_cmd(seen))
    monkeypatch.setattr(L, "COLD_MODE", "dgamr")
    res = L.call_agent("prompt", "m", f"test_cold_{tmp_path.name}")
    try:
        assert json.loads(json.loads(seen.read_text())) == {"target": "dgamr"}
        assert not (L.GUARD_STATE / "cold.json").exists()
    finally:
        for log in res["logs"]:
            (L.REPO_ROOT / log).unlink(missing_ok=True)


def test_no_marker_when_not_cold(tmp_path, monkeypatch):
    seen = tmp_path / "seen.json"
    monkeypatch.setattr(L, "_agent_argv", lambda template, model: _fake_cmd(seen))
    monkeypatch.setattr(L, "COLD_MODE", None)
    res = L.call_agent("prompt", "m", f"test_warm_{tmp_path.name}")
    try:
        assert json.loads(seen.read_text()) is None
    finally:
        for log in res["logs"]:
            (L.REPO_ROOT / log).unlink(missing_ok=True)


def test_marker_removed_even_if_agent_crashes(tmp_path, monkeypatch):
    def boom(*a, **k):
        assert (L.GUARD_STATE / "cold.json").exists()
        raise RuntimeError("agent crashed")
    monkeypatch.setattr(L, "COLD_MODE", "dgamr")
    monkeypatch.setattr(L.subprocess, "run", boom)
    try:
        L.call_agent("prompt", "m", f"test_crash_{tmp_path.name}")
    except RuntimeError:
        pass
    assert not (L.GUARD_STATE / "cold.json").exists()
    for f in (L.REPO_ROOT / "runs" / "kiro_sessions").glob(f"test_crash_{tmp_path.name}*"):
        f.unlink()
