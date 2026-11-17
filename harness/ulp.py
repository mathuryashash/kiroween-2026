"""
harness/ulp.py – ULP error and condition-aware allowance.

spec step 5: ulp(got, ref) = |got-ref| / spacing(|ref|_as_double)
  - ref is rounded to double once first
  - 0, inf, nan, subnormal handled
  - NaN/Inf got where ref finite -> inf ULP (counted, never skipped)

spec step 6: allowed(name, x) = max(4, ceil(2*kappa(x)))
  kappa = |x f'(x)/f(x)| via mpmath.diff at 50 digits
  Near zeros of f use absolute error fallback (kappa capped at 1e15).
"""

import math
import struct
import mpmath

mpmath.mp.dps = 50


def _double_spacing(x: float) -> float:
    """ULP size at |x|.  Handles zero (smallest subnormal) and subnormal."""
    ax = abs(x)
    if ax == 0.0:
        # spacing of 0 is the smallest positive subnormal
        return 5e-324
    sp = math.ulp(ax)
    if sp == 0.0:
        return 5e-324
    return sp


def ulp_error(got: float, ref: float) -> float:
    """ULP distance between got and the reference value.

    ref is treated as a high-precision value already rounded to the
    nearest double for the spacing denominator.
    """
    if got == ref:
        return 0.0

    # NaN or Inf in got while ref is finite -> infinite ULP
    if not math.isfinite(ref):
        # Both inf/nan: 0 if equal (handled above), else inf
        return float("inf")
    if not math.isfinite(got):
        return float("inf")

    sp = _double_spacing(ref)
    return abs(got - ref) / sp


# ---------------------------------------------------------------------------
# Condition-aware allowance
# ---------------------------------------------------------------------------

# Map routine name -> mpmath function
def _get_mpfn(name: str):
    """The referee function for a routine (one source of truth: oracle/referees.py)."""
    from oracle.referees import REFEREES
    ref = REFEREES.get(name)
    return ref["mpfn"] if ref else None


def allowed_ulp(name: str, x: float) -> float:
    """Return the condition-aware ULP allowance for f(x).

    allowed = max(4, ceil(2 * kappa))
    kappa = |x * f'(x) / f(x)|   computed with mpmath at 50 digits.
    Near zeros of f (|f(x)| < 1e-290), fall back to absolute error
    criterion: cap kappa at 1e15.
    """
    mpfn = _get_mpfn(name)
    if mpfn is None:
        return 4.0

    try:
        with mpmath.workdps(50):
            mx = mpmath.mpf(x)
            fx = mpfn(mx)
            if not mpmath.isfinite(fx):
                return 4.0
            if abs(fx) < mpmath.mpf("1e-290"):
                # near zero: absolute fallback, cap kappa
                kappa = mpmath.mpf("1e15")
            else:
                dfx = mpmath.diff(mpfn, mx)
                kappa = abs(mx * dfx / fx)
        return max(4.0, math.ceil(float(2 * kappa)))
    except Exception:
        return 4.0
