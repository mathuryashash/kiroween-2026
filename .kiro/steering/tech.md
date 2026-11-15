---
inclusion: always
---

# GALVANI – toolchain and repo layout

## Toolchain
- **Python**: `D:/hackathons/kiroween/.venv` (numpy, scipy, mpmath 1.4.1,
  hypothesis, pytest) — outside the repo; activate before running tests.
- **Fortran compiler**: resolve in order:
  1. `$GALVANI_FC` env var
  2. `D:/tools/winlibs/mingw64/bin/gfortran.exe` (GCC 16, 64-bit)
  3. `C:/MinGW/bin/gfortran.exe` (GCC 6.3, 32-bit x87 — last-bit differences
     possible; note in run JSON)
  Compile flags: `-std=legacy -O0 -w -ffloat-store -fno-fast-math`
- **mpmath referee**: 50 decimal digits minimum.
- **Kiro CLI**: `kiro-cli 3.2.1` on PATH; validate with
  `kiro-cli agent validate --path .kiro/agents/resurrector.json`

## Repo layout
```
.kiro/steering/      project-rules.md, product.md, tech.md,
                     fortran_translation.md, verification_rules.md
.kiro/agents/        resurrector.json
.kiro/hooks/         workspace hooks (non-blocking: trial-on-save logging)
.kiro/specs/         Kiro specs — the ONLY other place the agent may write
fortran/slatec/      SLATEC FNLIB sources + SOURCES.md (url, sha256, date)
fortran/support/     modern d1mach/i1mach/r1mach + xermsg stub
harness/             THE EXAM — protected, do not touch
oracle/              referee map — protected, do not touch
tests/               pytest — protected, do not touch
routines/            THE ONLY place the resurrector writes ports
runs/                committed trial outputs (JSON); numbers come from here
tools/guard/         anti-cheat guard — protected, do not touch
site/                static site (later chunk)
```

**Protected** = harness, oracle, tests, fortran, tools, runs, .kiro/steering,
.kiro/agents, .kiro/hooks.  The agent may only write to `routines/` and
`.kiro/specs/`.

## Key commands
```bash
# Validate agent config
kiro-cli agent validate --path .kiro/agents/resurrector.json

# Run a trial (once harness/ is built)
python -m harness.trial dgamma --impl port --n 2000 --seed 1

# Run pytest
pytest tests/ -q

# Fetch SLATEC source
python -m harness.fetch dgamma
```
