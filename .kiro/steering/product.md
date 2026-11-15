---
inclusion: always
---

# GALVANI – product context

## What GALVANI is
GALVANI uses Kiro to bring dead 1970s–1980s scientific Fortran (SLATEC FNLIB,
public domain) back to life as Python, and **proves every port**: the compiled
original Fortran, the Python port, and an independent 40–50-digit referee
(mpmath) all run on thousands of inputs.  Each routine receives a verdict:

| Verdict | Meaning |
|---------|---------|
| **RESURRECTED** | Port pass_rate ≥ 99 % on every sub-domain |
| **HEALED** | RESURRECTED *and* original pass_rate < 95 % on ≥ 1 sub-domain (we fixed a real bug) |
| **UNDEAD** | Port pass_rate ≥ 90 % on every sub-domain but not RESURRECTED |
| **STILL DEAD** | Otherwise, or the port crashes / is DISQUALIFIED |

## Honesty rules
- Every user-facing number (ULP, pass rate, credit count) must come from a run
  whose output JSON is committed under `runs/`.  Do not type numbers by hand.
- Claim wording: "the pipeline **re-found** it" — not "GALVANI found" — until a
  logged run exists that actually re-discovered the flaw without hints.
- "HEALED" requires both conditions.  Never call a port HEALED just because the
  original was bad; the port itself must pass the 99 % bar first.
- The Flaw Ledger lists only flaws that have been measured by the pipeline.
- SciPy comparison ("two graves"): frame as method validation and contribution,
  never as an attack; credit library maintainers by name.

## Scope
Floor 12 routines with full proof, target 25, stretch all 35 FNLIB double
1-argument functions.  HEALED ≥ 3 is the target.
