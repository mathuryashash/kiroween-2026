"""
tests/test_loop.py - the self-healing loop, end to end, with a scripted fake agent.

Each test builds a throwaway git repo with a clean exam, points harness.loop at it, replaces only
the trial (a toy pass-rate model of the port's text, so no gfortran is needed) and runs the real
loop: real git commits, real agent subprocess (tests/fixtures/fake_agent.py), real prompt files.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import harness.loop as L

FAKE = Path(__file__).parent / "fixtures" / "fake_agent.py"

BUGGY = "import math\n\ndef toy(x):\n    s = x + 1 - 1\n    t = 2.0\n    return s * t\n"


def _git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, check=True).stdout


@pytest.fixture
def repo(tmp_path, monkeypatch):
    r = tmp_path / "repo"
    for d in ("routines", "harness", "oracle", "tests", "fortran", "tools",
              ".kiro/steering", ".kiro/agents", ".kiro/hooks"):
        (r / d).mkdir(parents=True)
        (r / d / "keep.txt").write_text("exam", encoding="utf-8")
    (r / "routines" / "toy.py").write_text(BUGGY, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    _git(r, "config", "core.autocrlf", "false")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "init")
    monkeypatch.setattr(L, "REPO_ROOT", r)
    monkeypatch.setattr(L, "RETRY_WAITS_S", (0, 0))
    monkeypatch.setattr(L, "build_feedback", lambda t: "FEEDBACK: tiny fails\n")
    monkeypatch.setattr(L, "build_autopsy", lambda name, xs: f"AUTOPSY of {xs}\n")
    monkeypatch.setattr(L, "build_ablation", lambda name, a, b: f"ABLATION {a[:7]}..{b[:7]}\n")
    monkeypatch.setattr(L, "build_transcription", lambda name: "")
    return r


def toy_trial(repo):
    """Pass rates computed from the port's text: 'x + (1 - 1)' heals tiny, 't = 3.0' breaks mid."""
    calls = []

    def trial(name, seed, n, label, dry=False):
        src = (repo / "routines" / f"{name}.py").read_text(encoding="utf-8")
        tiny = 100.0 if "x + (1 - 1)" in src else 0.0
        mid = 50.0 if "t = 3.0" in src else 100.0
        stats = {"tiny": {"pass_rate": tiny, "max_ulp": 1e9 if tiny < 99 else 1.0, "worst_x": 1.234567e-9},
                 "mid": {"pass_rate": mid, "max_ulp": 9.0 if mid < 99 else 1.0, "worst_x": 2.5}}
        verdict = "HEALED" if tiny == 100.0 and mid == 100.0 else "STILL DEAD"
        res = {"verdict": verdict, "overall_pass_rate": (tiny + mid) / 2, "domain_stats": stats,
               "original_on_same_inputs": {"tiny": {"pass_rate": 0.0}, "mid": {"pass_rate": 100.0}}}
        calls.append((seed, n, verdict))
        if dry:
            return res, None
        p = repo / "runs" / name / f"port_{len(calls)}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(res), encoding="utf-8")
        L._commit(f"{name} {label} trial: {verdict}", [p])
        return res, p

    trial.calls = calls
    return trial


def script(tmp_path, steps, name="toy"):
    s = tmp_path / "script.json"
    s.write_text(json.dumps({"name": name, "next": 0, "steps": steps}), encoding="utf-8")
    return s


def run(repo, tmp_path, monkeypatch, steps, **kw):
    s = script(tmp_path, steps)
    trial = toy_trial(repo)
    monkeypatch.setattr(L, "trial_port", trial)
    led = L.loop("toy", agent_cmd=[sys.executable, str(FAKE), str(s)], start="repair", **kw)
    return led, json.loads(s.read_text(encoding="utf-8")), trial


def test_heals_and_confirms_on_heldout(repo, tmp_path, monkeypatch):
    led, st, trial = run(repo, tmp_path, monkeypatch, [{"edit": ["x + 1 - 1", "x + (1 - 1)"], "credits": 0.3}])
    assert led["stop_reason"] == "healed_confirmed" and led["result"] == "HEALED"
    assert [c[:2] for c in trial.calls] == [L.DEV, L.DEV, L.HELDOUT]
    assert led["total_credits"] == pytest.approx(0.3)
    log = _git(repo, "log", "--format=%s")
    assert "toy round 1 by Kiro resurrector on claude-haiku-4.5 (verbatim, 0.30 credits)" in log
    assert (repo / "routines" / "toy.py").read_text(encoding="utf-8").count("x + (1 - 1)") == 1
    assert _git(repo, "status", "--porcelain") == ""                 # everything is committed
    assert "FEEDBACK" in st["prompts"][0] and "AUTOPSY" in st["prompts"][0]


def test_two_changes_one_bad_is_undone_with_a_new_commit(repo, tmp_path, monkeypatch):
    steps = [{"edit": ["x + 1 - 1\n    t = 2.0", "x + (1 - 1)\n    t = 3.0"]},   # heals tiny, breaks mid
             {"edit": ["x + 1 - 1", "x + (1 - 1)"]}]                             # the clean fix
    led, st, _ = run(repo, tmp_path, monkeypatch, steps)
    kinds = [r["type"] for r in led["rounds"]]
    assert kinds == ["reverted", "repair"] and led["stop_reason"] == "healed_confirmed"
    assert "mid 100.00% -> 50.00%" in led["rounds"][0]["regressions"][0]
    # round 2's prompt carries the ablation of round 1 and the undone diff
    assert "ABLATION" in st["prompts"][1] and "UNDONE because it made the port worse" in st["prompts"][1]
    assert "+    t = 3.0" in st["prompts"][1]
    # history was never rewritten: the bad round is still in the log, followed by its undo
    log = _git(repo, "log", "--format=%s")
    assert "toy round 1 undone: it made the port worse" in log and "toy round 1 by Kiro" in log


def test_overfit_guard_undoes_a_special_case(repo, tmp_path, monkeypatch):
    steps = [{"edit": ["    s = x + 1 - 1", "    if x == 1.234567e-9:\n        return 0.0\n    s = x + 1 - 1"]},
             {"edit": ["t = 2.0", "t = 2.0  # x=1.234567e-9 noted in a comment is fine"]}]
    led, _, _ = run(repo, tmp_path, monkeypatch, steps)
    assert led["rounds"][0]["type"] == "rejected"
    assert "1.234567e-9" in led["rounds"][0]["overfit"][0]
    assert "if x ==" not in (repo / "routines" / "toy.py").read_text(encoding="utf-8")
    assert led["rounds"][1]["type"] != "rejected"                    # comments are not code


def test_heldout_disagreement_is_not_a_success(repo, tmp_path, monkeypatch):
    s = script(tmp_path, [{"edit": ["x + 1 - 1", "x + (1 - 1)"]}])
    inner = toy_trial(repo)

    def trial(name, seed, n, label, dry=False):           # passes the dev inputs, fails held-out
        res, p = inner(name, seed, n, label, dry)
        if seed == L.HELDOUT[0]:
            res = {**res, "verdict": "STILL DEAD"}
        return res, p

    monkeypatch.setattr(L, "trial_port", trial)
    led = L.loop("toy", agent_cmd=[sys.executable, str(FAKE), str(s)], start="repair")
    assert led["stop_reason"] == "heldout_disagrees" and led["result"] is None


def test_no_diff_twice_stops(repo, tmp_path, monkeypatch):
    led, _, _ = run(repo, tmp_path, monkeypatch, [{"say": "nothing to do"}, {"say": "still nothing"}])
    assert led["stop_reason"] == "no_diff_twice" and len(led["rounds"]) == 2


def test_round_without_gain_is_undone_and_two_stop_the_loop(repo, tmp_path, monkeypatch):
    steps = [{"edit": ["t = 2.0", "t = 2.0 "]}, {"edit": ["s = x", "s =  x"]}, {"say": "unused"}]
    led, st, _ = run(repo, tmp_path, monkeypatch, steps)
    assert [r["type"] for r in led["rounds"]] == ["no_gain", "no_gain"]
    assert led["stop_reason"] == "two_failed_rounds_in_a_row" and len(st["prompts"]) == 2
    assert (repo / "routines" / "toy.py").read_text(encoding="utf-8") == BUGGY
    assert "UNDONE because no sub-domain improved" in st["prompts"][1]


def test_credit_cap_stops_before_overspending(repo, tmp_path, monkeypatch):
    steps = [{"edit": ["t = 2.0", "t = 2.0 "], "credits": 1.5}] * 5
    led, _, _ = run(repo, tmp_path, monkeypatch, steps, credit_cap=2.5, max_rounds=5)
    assert led["stop_reason"].startswith("credit_cap") and led["total_credits"] <= 2.5


def test_throttle_is_retried_then_succeeds(repo, tmp_path, monkeypatch):
    steps = [{"fail": 1, "stderr": "429 CREDIT_CONSUMPTION_RATE_EXCEEDED", "credits": 0.0},
             {"edit": ["x + 1 - 1", "x + (1 - 1)"], "credits": 0.2}]
    led, st, _ = run(repo, tmp_path, monkeypatch, steps)
    assert led["stop_reason"] == "healed_confirmed" and len(st["prompts"]) == 2


def test_agent_writing_outside_routines_stops_the_loop(repo, tmp_path, monkeypatch):
    led, _, _ = run(repo, tmp_path, monkeypatch, [{"touch": "harness/evil.py"}])
    assert led["stop_reason"].startswith("files outside routines/ changed")


def test_preflight_refuses_a_dirty_exam(repo, tmp_path, monkeypatch):
    (repo / "oracle" / "new.py").write_text("x", encoding="utf-8")
    led, st, trial = run(repo, tmp_path, monkeypatch, [{"say": "unused"}])
    assert led["error"] == "exam_dirty" and trial.calls == [] and "prompts" not in st


def test_blind_port_then_repair(repo, tmp_path, monkeypatch):
    (repo / "routines" / "toy.py").unlink()
    _git(repo, "commit", "-qam", "remove port")
    s = script(tmp_path, [{"write": BUGGY, "say": "translated"}, {"edit": ["x + 1 - 1", "x + (1 - 1)"]}])
    monkeypatch.setattr(L, "trial_port", toy_trial(repo))
    led = L.loop("toy", agent_cmd=[sys.executable, str(FAKE), str(s)], start="port")
    assert [r["type"] for r in led["rounds"]] == ["port", "repair"]
    assert led["stop_reason"] == "healed_confirmed"
    first = json.loads(s.read_text(encoding="utf-8"))["prompts"][0]
    assert "Translate literally" in first and "x + (1 - 1)" not in first


def test_transcription_errors_lead_the_prompt(repo, tmp_path, monkeypatch):
    monkeypatch.setattr(L, "build_transcription", lambda name: "1 of 2 DATA constants differ: CS(3)\n")
    _, st, _ = run(repo, tmp_path, monkeypatch, [{"edit": ["x + 1 - 1", "x + (1 - 1)"]}])
    p = st["prompts"][0]
    assert p.index("TRANSCRIPTION CHECK") < p.index("TRIAL REPORT") and "CS(3)" in p


def test_prompts_carry_no_fix_hint():
    for text in (L.blind_port_prompt("dcot"), L.repair_prompt("dcot", 1, 4, "", "F", "A", "")):
        for leak in ("X+I-1", "x + (i - 1)", "DBLE(I-1)", "1.0D0/Y", "1.0/y", "X*X/SQRTPI"):
            assert leak.lower() not in text.lower()


def test_overfit_check_ignores_constants_and_existing_literals():
    diff = ("+    y = 0.6366197723675814 * x\n"     # 2/pi
            "+    if x > 1.2345e-9:\n"              # only 5 digits, matches a shown input
            "+    z = 0.9375 + y\n")                # already in the code
    out = L.check_overfit(diff, [1.2345e-9, 2.5], before_text="z = 0.9375")
    assert len(out) == 1 and "1.2345e-9" in out[0]
