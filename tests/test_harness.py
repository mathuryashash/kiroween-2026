"""
tests/test_harness.py  –  pytest suite for GALVANI chunk 1 (harness exam).

Tests are intentionally written BEFORE the harness modules are fully
implemented.  Run:  pytest -q tests/test_harness.py
"""
import sys, math, pytest

# ---------------------------------------------------------------------------
# 1. Parser tests  (spec step 3)
# ---------------------------------------------------------------------------
def test_parse_normal():
    from harness.parse import parse_fortran_float
    assert parse_fortran_float("  1.23456789012345678E+00") == pytest.approx(1.23456789012345678)

def test_parse_1e300():
    from harness.parse import parse_fortran_float
    val = parse_fortran_float("  1.0E+300")
    assert val == pytest.approx(1e300, rel=1e-14)

def test_parse_missing_e_exponent():
    """Fortran ES25.17 with 3-digit exponent: 'E' may be omitted -> 5.39....-176."""
    from harness.parse import parse_fortran_float
    s = "  5.39586561160790118-176"
    val = parse_fortran_float(s)
    assert math.isfinite(val)
    assert val == pytest.approx(5.39586561160790118e-176, rel=1e-14)

def test_parse_garbage_raises():
    from harness.parse import parse_fortran_float, ParseError
    with pytest.raises(ParseError):
        parse_fortran_float("not_a_number")

def test_parse_garbage_with_lineno():
    from harness.parse import parse_fortran_lines
    with pytest.raises(Exception) as exc_info:
        parse_fortran_lines(["1.0E+00", "garbage_line", "2.0E+00"])
    assert "2" in str(exc_info.value)  # line number reported


# ---------------------------------------------------------------------------
# 2. ULP distance  (spec step 5)
# ---------------------------------------------------------------------------
def test_ulp_zero():
    from harness.ulp import ulp_error
    assert ulp_error(1.0, 1.0) == 0.0

def test_ulp_one_bit():
    import struct
    from harness.ulp import ulp_error
    # next representable double after 1.0
    bits = struct.unpack("Q", struct.pack("d", 1.0))[0] + 1
    nxt = struct.unpack("d", struct.pack("Q", bits))[0]
    assert ulp_error(nxt, 1.0) == pytest.approx(1.0, abs=0.01)

def test_ulp_nan_got():
    from harness.ulp import ulp_error
    assert ulp_error(float("nan"), 1.0) == float("inf")

def test_ulp_inf_got_finite_ref():
    from harness.ulp import ulp_error
    assert ulp_error(float("inf"), 1.0) == float("inf")

def test_ulp_zero_ref():
    """When ref == 0 use absolute spacing."""
    from harness.ulp import ulp_error
    # any non-zero got vs ref=0 -> inf ULP (spacing of 0 is smallest subnormal)
    assert ulp_error(1e-320, 0.0) > 0

def test_ulp_subnormal():
    from harness.ulp import ulp_error
    import sys
    subnorm = 5e-324
    assert ulp_error(subnorm * 2, subnorm) >= 1.0


# ---------------------------------------------------------------------------
# 3. Condition-aware allowance  (spec step 6)
# ---------------------------------------------------------------------------
def test_allowance_mid():
    from harness.ulp import allowed_ulp
    # gamma(2.0) = 1.0 exact; condition number is small
    a = allowed_ulp("dgamma", 2.0)
    assert a >= 4

def test_allowance_tiny():
    from harness.ulp import allowed_ulp
    # kappa(dgamma, x) = |x * psi(x)| ≈ |x * (-1/x)| = 1 near 0
    # so allowed = max(4, ceil(2*1)) = 4; the big ULP errors from the
    # original are algorithmic cancellation, not conditioning.
    a = allowed_ulp("dgamma", 1e-10)
    assert a >= 4  # condition-aware floor


# ---------------------------------------------------------------------------
# 4. Verdict logic  (spec step 7)
# ---------------------------------------------------------------------------
def test_verdict_resurrected():
    from harness.verdict import compute_verdict
    # All sub-domains >= 99% pass rate -> RESURRECTED
    stats = {
        "tiny": {"pass_rate": 99.5},
        "small": {"pass_rate": 100.0},
        "mid": {"pass_rate": 100.0},
        "large": {"pass_rate": 99.1},
        "negative": {"pass_rate": 99.2},
    }
    v = compute_verdict(stats, original_stats=None)
    assert v == "RESURRECTED"

def test_verdict_healed():
    from harness.verdict import compute_verdict
    # Port >= 99% on all; original < 95% on some
    port_stats = {d: {"pass_rate": 99.5} for d in ["tiny","small","mid","large","negative"]}
    orig_stats = {
        "tiny": {"pass_rate": 10.0},   # bad original
        "small": {"pass_rate": 100.0},
        "mid": {"pass_rate": 100.0},
        "large": {"pass_rate": 100.0},
        "negative": {"pass_rate": 100.0},
    }
    v = compute_verdict(port_stats, original_stats=orig_stats)
    assert v == "HEALED"

def test_verdict_undead():
    from harness.verdict import compute_verdict
    stats = {d: {"pass_rate": 92.0} for d in ["tiny","small","mid","large","negative"]}
    v = compute_verdict(stats, original_stats=None)
    assert v == "UNDEAD"

def test_verdict_still_dead():
    from harness.verdict import compute_verdict
    stats = {d: {"pass_rate": 80.0} for d in ["tiny","small","mid","large","negative"]}
    v = compute_verdict(stats, original_stats=None)
    assert v == "STILL DEAD"

def test_verdict_disqualified():
    from harness.verdict import compute_verdict
    v = compute_verdict(None, original_stats=None, disqualified=True)
    assert v == "DISQUALIFIED"


# ---------------------------------------------------------------------------
# 5. Port AST import guard  (spec step 8)
# ---------------------------------------------------------------------------
def test_guard_allows_math_import(tmp_path):
    from harness.port_guard import check_port_ast
    code = "import math\ndef dgamma(x):\n    return math.gamma(x)\n"
    p = tmp_path / "dgamma.py"
    p.write_text(code)
    ok, reason = check_port_ast(str(p))
    assert ok, reason

def test_guard_allows_from_math_import(tmp_path):
    from harness.port_guard import check_port_ast
    code = "from math import gamma\ndef dgamma(x):\n    return gamma(x)\n"
    p = tmp_path / "dgamma.py"
    p.write_text(code)
    ok, reason = check_port_ast(str(p))
    assert ok, reason

def test_guard_blocks_import_numpy(tmp_path):
    from harness.port_guard import check_port_ast
    code = "import numpy\ndef dgamma(x):\n    return float(numpy.math.gamma(x))\n"
    p = tmp_path / "dgamma.py"
    p.write_text(code)
    ok, reason = check_port_ast(str(p))
    assert not ok

def test_guard_blocks_open(tmp_path):
    from harness.port_guard import check_port_ast
    code = "import math\ndef dgamma(x):\n    open('/tmp/x')\n    return math.gamma(x)\n"
    p = tmp_path / "dgamma.py"
    p.write_text(code)
    ok, reason = check_port_ast(str(p))
    assert not ok

def test_guard_blocks_exec(tmp_path):
    from harness.port_guard import check_port_ast
    code = "def dgamma(x):\n    exec('pass')\n    return 1.0\n"
    p = tmp_path / "dgamma.py"
    p.write_text(code)
    ok, reason = check_port_ast(str(p))
    assert not ok

def test_guard_blocks_dunder(tmp_path):
    from harness.port_guard import check_port_ast
    code = "def dgamma(x):\n    return x.__class__.__name__\n"
    p = tmp_path / "dgamma.py"
    p.write_text(code)
    ok, reason = check_port_ast(str(p))
    assert not ok

def test_port_import_guard_disqualifies(tmp_path, monkeypatch):
    """Loading a port with a banned import raises and returns DISQUALIFIED."""
    from harness.port_guard import load_port
    code = "import os\ndef dgamma(x):\n    return float(os.getpid())\n"
    p = tmp_path / "dgamma.py"
    p.write_text(code)
    with pytest.raises(Exception, match="DISQUALIFIED"):
        load_port(str(p), "dgamma")
