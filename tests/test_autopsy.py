"""Autopsy (shadow-value tracing) must find a planted cancellation and stay quiet on clean code."""
from pathlib import Path

import mpmath

from harness.autopsy import autopsy, format_report, ulp_diff

TOY_BAD = """import math

def toy(x):
    n = 1
    s = math.exp(x)
    for i in range(1, n + 1):
        s = s / (x + i - 1)
    return s
"""

TOY_GOOD = """import math

def toy(x):
    n = 1
    s = math.exp(x)
    for i in range(1, n + 1):
        s = s / (x + float(i - 1))
    return s
"""

TOY_HELPER = """import math

def _h(x):
    t = 1.0 + x
    return t - 1.0

def toy(x):
    y = 2.0 * x
    return math.exp(1.0) / _h(y)
"""


def _write(tmp_path, src):
    p = tmp_path / "toy.py"
    p.write_text(src, encoding="utf-8")
    return p


def test_finds_planted_cancellation(tmp_path):
    a = autopsy("toy", 1e-9, port_path=_write(tmp_path, TOY_BAD))
    assert a["result_ulp"] > 1e6
    c = a["chain"][0]
    assert c["line"] == 7 and c["var"] == "s"
    lost = [r for r in c["subexpressions"] if r["lost_here"]]
    assert [r["expr"] for r in lost] == ["x + i - 1"]
    assert "cancellation" in lost[0]["note"]
    assert "digits lost here" in format_report(a)


def test_clean_code_reports_nothing(tmp_path):
    a = autopsy("toy", 1e-9, port_path=_write(tmp_path, TOY_GOOD))
    assert a["result_ulp"] <= 1.0
    assert a["chain"] == []


def test_drills_into_helper(tmp_path):
    a = autopsy("toy", 1e-10, port_path=_write(tmp_path, TOY_HELPER))
    funcs = [c["func"] for c in a["chain"]]
    assert funcs == ["toy", "_h"], funcs
    lost = [r["expr"] for r in a["chain"][1]["subexpressions"] if r["lost_here"]]
    assert lost == ["t - 1.0"]


TOY_LOGIC = """import math

def toy(x):
    u = x + 3.0
    s = 0.0
    for k in range(1, 4):
        s += u ** k
    return math.exp(s) + x
"""


def test_logic_error_gets_logic_trace(tmp_path):
    a = autopsy("toy", 0.5, port_path=_write(tmp_path, TOY_LOGIC), reference=lambda v: v)
    assert a["shadow_vs_reference_ulp"] > 1e6
    tr = a["logic_trace"]
    assert tr[0]["var"] == "u" and float(tr[0]["shadow"]) == 3.5
    loop = [t for t in tr if t["var"] == "s" and t["repeats"]]
    assert loop and loop[0]["repeats"] == 2
    assert "ALSO wrong" in format_report(a)


def test_ulp_diff_basics():
    assert ulp_diff(1.0, mpmath.mpf(1)) == 0.0
    assert abs(ulp_diff(1.0 + 2.0 ** -52, mpmath.mpf(1)) - 1.0) < 1e-9
    assert ulp_diff(float("nan"), mpmath.nan) == 0.0
