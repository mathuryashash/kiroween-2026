"""
tests/test_loop_disqualified.py: the loop must not crash when the trial is DISQUALIFIED.

Loop run dlngam 20261124T040948Z crashed with KeyError 'overall_pass_rate' while writing the
commit message for a DISQUALIFIED trial (the port had a SyntaxError). The verdict was right;
only the message formatting failed, so the loop never reached its own stop and ledger.
"""

import harness.loop as L


def test_trial_port_commit_message_for_disqualified(monkeypatch, tmp_path):
    dq = {"verdict": "DISQUALIFIED", "impl": "port", "name": "dlngam",
          "error": "DISQUALIFIED: SyntaxError: leading zeros in decimal integer literals\nsecond line"}
    run_file = tmp_path / "port_x.json"
    run_file.write_text("{}", encoding="utf-8")
    msgs = []
    import harness.trial as T
    monkeypatch.setattr(T, "run_trial", lambda name, impl, n, seed: dq)
    monkeypatch.setattr(T, "write_run", lambda name, impl, result: run_file)
    monkeypatch.setattr(L, "_commit", lambda message, files: msgs.append(message) or "abc")
    result, path = L.trial_port("dlngam", 1, 2000, label="dev")
    assert result["verdict"] == "DISQUALIFIED"
    assert msgs == ["dlngam dev trial (seed 1, n=2000): DISQUALIFIED "
                    "DISQUALIFIED: SyntaxError: leading zeros in decimal integer literals"]


def test_trial_port_commit_message_with_rate(monkeypatch, tmp_path):
    ok = {"verdict": "STILL DEAD", "overall_pass_rate": 51.0}
    run_file = tmp_path / "port_y.json"
    run_file.write_text("{}", encoding="utf-8")
    msgs = []
    import harness.trial as T
    monkeypatch.setattr(T, "run_trial", lambda name, impl, n, seed: ok)
    monkeypatch.setattr(T, "write_run", lambda name, impl, result: run_file)
    monkeypatch.setattr(L, "_commit", lambda message, files: msgs.append(message) or "abc")
    L.trial_port("dgamr", 1, 2000, label="dev")
    assert msgs == ["dgamr dev trial (seed 1, n=2000): STILL DEAD 51.00%"]
