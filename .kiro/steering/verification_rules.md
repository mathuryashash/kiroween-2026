---
inclusion: always
---

# Verification rules (identical to harness/trial definitions)

These numbers are authoritative; harness/trial.py uses the same values.

## ULP metric
`ulp(x) = |got - ref| / spacing(|ref| as double)`
where `ref` is rounded once to double before spacing is computed.
Special cases:
- `ref` is 0: use absolute error `|got - ref|`.
- `got` is NaN or Inf where `ref` is finite: ULP = ∞ (counted, never skipped).
- Subnormal `ref`: use `spacing(sys.float_info.min)` as the unit.

## Condition-aware allowance
`kappa(x) = |x · f′(x) / f(x)|` computed with mpmath at 50 digits via
`mpmath.diff`.
`allowed(x) = max(4, ceil(2 · kappa(x)))`
Near zeros of `f`: use absolute error fallback with allowance 4.

## Verdicts
`pass(x) = ulp(x) <= allowed(x)`

| Verdict | Condition |
|---------|-----------|
| **RESURRECTED** | Port `pass_rate ≥ 99.0 %` on **every** sub-domain |
| **HEALED** | RESURRECTED **and** original `pass_rate < 95.0 %` on **at least one** sub-domain |
| **UNDEAD** | Port `pass_rate ≥ 90.0 %` on every sub-domain but not RESURRECTED |
| **STILL DEAD** | Otherwise, or the port crashes or is DISQUALIFIED |

## DISQUALIFIED
An AST check before import blocks: any import other than `math`; use of `open`,
`exec`, `eval`, `__import__`, `compile`, `globals`, `getattr` on modules, dunder
attribute access.  Verdict is DISQUALIFIED — shown in output, never hidden.

## Per-sub-domain stats written to run JSON
`pass_rate`, `max_ulp`, `median_ulp`, `p99_ulp`, `worst_x` per sub-domain and
overall.  Also: toolchain (gfortran version, python, numpy, mpmath, scipy),
git commit of repo, sha256 manifest of every harness/oracle/fortran file used.
