# harness/ – the GALVANI exam

The harness is the **protected exam** that evaluates a Fortran-to-Python port of an SLATEC FNLIB routine.

## CLI

```bash
# Fetch sources (idempotent, caches in fortran/slatec/)
python -m harness.fetch dgamma

# Run a trial
python -m harness.trial dgamma --impl original|fixed-original|port|scipy --n N --seed S
```

The trial writes `runs/<name>/<impl>_<UTCstamp>.json` and updates `runs/<name>/latest.json`.

## Implementations

| `--impl`         | Description |
|------------------|-------------|
| `original`       | Netlib SLATEC DGAMMA (buggy 1989 version) |
| `fixed-original` | One-line fix: `X+DBLE(I-1)` instead of `X+I-1` |
| `port`           | Python port in `routines/<name>.py` |
| `scipy`          | `scipy.special.gamma` etc. |

## Verdict rules

| Verdict       | Condition |
|---------------|-----------|
| `DISQUALIFIED`| Port crashed or failed AST check |
| `RESURRECTED` | Port pass_rate ≥ 99% on **every** sub-domain |
| `HEALED`      | RESURRECTED **and** original < 95% on ≥ 1 sub-domain |
| `UNDEAD`      | Port pass_rate ≥ 90% on every sub-domain (not RESURRECTED) |
| `STILL DEAD`  | Otherwise |

## Pass criterion

`pass(x) = ulp(x) <= allowed(x)`

where `allowed(x) = max(4, ceil(2 * kappa(x)))` and `kappa = |x·f'(x)/f(x)|` via mpmath at 50 digits.

## Port import rules (enforced by AST before import)

Only `import math` and `from math import ...` are allowed.
Banned: any other import, `open`, `exec`, `eval`, `__import__`, `compile`, `globals`, `getattr`, dunder attribute access.
Violations → `DISQUALIFIED`.

## Sub-domains for dgamma

| Domain   | Range              | Sampling    |
|----------|--------------------|-------------|
| tiny     | (1e-12, 1e-3)      | log-uniform |
| small    | (1e-3, 1)          | log-uniform |
| mid      | (1, 30)            | log-uniform |
| large    | (30, 171)          | log-uniform |
| negative | (−30, 0) non-int   | log-uniform |
