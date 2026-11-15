"""Port isolation, verdict and exam-integrity tests (added after chunk-1/2 review)."""
import subprocess
import sys
from pathlib import Path

from harness.port_guard import check_port_ast
from harness.verdict import compute_verdict

REPO = Path(__file__).resolve().parent.parent


def _runner(port_file: Path, name: str, xs):
    return subprocess.run(
        [sys.executable, "-m", "harness.port_runner", str(port_file), name],
        input="".join(repr(float(x)) + "\n" for x in xs),
        capture_output=True, text=True, cwd=str(REPO), timeout=60,
    )


def test_port_runner_evaluates_in_subprocess(tmp_path):
    p = tmp_path / "toy.py"
    p.write_text("import math\n\ndef toy(x):\n    return math.gamma(x)\n", encoding="utf-8")
    r = _runner(p, "toy", [5.0, 0.5])
    assert r.returncode == 0, r.stderr
    vals = [float(v) for v in r.stdout.split()]
    assert vals[0] == 24.0 and abs(vals[1] - 1.7724538509055159) < 1e-15


def test_port_runner_exception_becomes_nan(tmp_path):
    p = tmp_path / "boom.py"
    p.write_text("def boom(x):\n    return 1.0 / (x - 1.0)\n", encoding="utf-8")
    r = _runner(p, "boom", [1.0, 2.0])
    assert r.returncode == 0
    assert r.stdout.split() == ["nan", "1.0"]


def test_port_runner_disqualifies_bad_import(tmp_path):
    p = tmp_path / "bad.py"
    p.write_text("import scipy.special\n\ndef bad(x):\n    return x\n", encoding="utf-8")
    r = _runner(p, "bad", [1.0])
    assert r.returncode == 3 and "DISQUALIFIED" in r.stderr


def _ast_ok(tmp_path, src):
    p = tmp_path / "t.py"
    p.write_text(src, encoding="utf-8")
    return check_port_ast(str(p))[0]


def test_ast_blocks_builtins_and_frames(tmp_path):
    assert not _ast_ok(tmp_path, "def f(x):\n    return __builtins__\n")
    assert not _ast_ok(tmp_path, "def f(x):\n    g = vars\n    return x\n")
    assert not _ast_ok(tmp_path, "import math\ndef f(x):\n    return math.f_globals\n")
    assert not _ast_ok(tmp_path, "def f(x):\n    return setattr(x, 'a', 1)\n")
    assert _ast_ok(tmp_path, "import math\nfrom math import log\ndef f(x):\n    return math.exp(log(x))\n")


def test_verdict_healed_needs_broken_original():
    good = {"tiny": {"pass_rate": 100.0}, "mid": {"pass_rate": 99.5}}
    broken_orig = {"tiny": {"pass_rate": 0.0}, "mid": {"pass_rate": 100.0}}
    fine_orig = {"tiny": {"pass_rate": 99.0}, "mid": {"pass_rate": 100.0}}
    assert compute_verdict(good, broken_orig) == "HEALED"
    assert compute_verdict(good, fine_orig) == "RESURRECTED"
    assert compute_verdict({"tiny": {"pass_rate": 50.0}}, broken_orig) == "STILL DEAD"
    assert compute_verdict({"tiny": {"pass_rate": 95.0}}, broken_orig) == "UNDEAD"


def test_exam_dirty_lists_untracked_exam_file():
    from harness.trial import _exam_dirty
    probe = REPO / "oracle" / "_dirty_probe_tmp.py"
    probe.write_text("# temp\n", encoding="utf-8")
    try:
        assert any("_dirty_probe_tmp.py" in f for f in _exam_dirty())
    finally:
        probe.unlink()
