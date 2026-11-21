# Cold Test of Remaining Flawed Originals – Design

## Component Overview

The cold test feature integrates the following existing components:

- **harness.loop**: Orchestrates rounds of agent edits and trials; enforces credit cap (default 1.5), failed-round counter, frozen-tag check, and stops after two consecutive failures.
- **harness.trial**: Runs the exam (original Fortran + port + mpmath referee) on a given routine and sub-domain range, outputs JSON with pass rates, ULP stats, and verdict.
- **harness.autopsy**: Analyzes a failed trial to suggest which input range or code line failed and why.
- **harness.transcription**: Checks that DATA constants are copied correctly from Fortran to Python (AST verification before import).
- **harness.port_guard**: AST check (before import) that rejects ports importing anything other than `math`, or using open/exec/eval/__import__/compile/globals or dunder attributes; verdict is DISQUALIFIED.
- **harness.port_runner**: Runs the port in a separate process.
- **harness.verdict**: Computes verdicts from pass rates.
- **resurrector agent**: Invoked as `kiro-cli chat --v3 --no-interactive --trust-all-tools --agent resurrector --model {model} --output-format stream-json "<prompt>"`; receives autopsy hints; edits routines/<name>.py to fix failing cases.
- **guard hooks** (.kiro/hooks): Block reads/writes to protected files; mark trial VOID (stop reason "exam files changed during the round") if exam paths change.
- **site/tools/build.py**: Reads committed run JSON files and renders the ledger and routine pages.

## Data Flow of One Cold Test Round

```
1. User invokes: python -m harness.loop <routine> --model claude-haiku-4.5 [--credit-cap 1.5]

2. Loop preflight checks:
   - Git diff loop-frozen-1 -- harness oracle tests fortran tools .kiro/steering .kiro/agents .kiro/hooks empty? If not, output VOID (stop reason "exam files changed during the round"), exit.
   - Routine in list of flawed originals (DPSI, DLNGAM, DGAMR)? If not, error.

3. Trial execution (harness.trial):
   - Compile Fortran original (or use fortran/variants/ if available).
   - Import Python port from routines/<routine>.py; harness.port_guard AST check rejects non-math imports, open/exec/eval/__import__/compile/globals, dunder attributes → DISQUALIFIED.
   - For each sub-domain (tiny, small, negative, etc.):
     a. Generate test inputs (via hypothesis or fixed seed).
     b. Call Fortran original, Python port, mpmath referee on each input.
     c. Compute ULP(x) for each input; check pass(x) = ulp(x) <= allowed(x).
     d. Record pass_rate, max_ulp, median_ulp, p99_ulp, worst_x.
   - Aggregate across sub-domains; determine verdict.
   - Per-trial check: if exam files changed, mark VOID.

4. Verdict interpretation:
   - RESURRECTED: port pass_rate ≥ 99.0% on all sub-domains.
   - HEALED: RESURRECTED AND original pass_rate < 95.0% on at least one sub-domain AND held-out trial also RESURRECTED.
   - UNDEAD: port pass_rate ≥ 90.0% on all sub-domains but not RESURRECTED.
   - STILL DEAD: port pass_rate < 90.0% on any sub-domain, or AST violation (DISQUALIFIED), or crash.

5. Round accounting:
   - Loop charges 0.75 credits per dev trial.
   - If verdict == UNDEAD or STILL DEAD: failed-round counter += 1.
   - If failed-round counter >= 2: stop further rounds, record stop reason "two_failed_rounds_in_a_row", exit.
   - Before starting a round, if spent + estimate > credit_cap: stop, record stop reason "credit_cap (...)", exit.

6. Held-out trial (after RESURRECTED):
   - Loop schedules held-out trial (seed 7, n=10000, hidden from agent) in separate process.
   - Result recorded in run JSON under `heldout` with keys seed, n, verdict, file.
   - If held-out RESURRECTED: routine becomes HEALED candidate.
   - If held-out UNDEAD/STILL DEAD: routine marked with that verdict.

7. Autopsy (if UNDEAD/STILL DEAD and < 2 failures):
   - harness.autopsy reads run JSON; identifies worst-failing sub-domain and input(s).
   - Outputs hint text (sub-domain, failing input X, magnitude of error, likely line).

8. Agent invocation (if continuing):
   - Loop invokes: kiro-cli chat --v3 --no-interactive --trust-all-tools --agent resurrector --model {model} --output-format stream-json "<prompt>"
   - Prompt includes routine name, autopsy hints, Fortran source.
   - Agent edits routines/<routine>.py to fix failing case(s).
   - Agent returns; loop checks for AST violations.
   - If AST clean: loop goes to step 3 (new trial). Else: DISQUALIFIED, exit.

9. Run JSON generation:
   - harness.transcription writes: toolchain (gfortran, Python, numpy, mpmath, scipy versions), git commit hash, sha256 manifest of harness/, oracle/, routines/<routine>.py.
   - Loop writes final run JSON to runs/ledger/<routine>_<run_id>.json with keys: name, model, run_id, max_rounds, credit_cap, dev {seed, n}, heldout {seed, n, verdict, file}, start_commit, rounds[], total_credits, stop_reason, result.

10. Output:
    - Commit run JSON to git.
    - Optionally invoke site/tools/build.py to render ledger and routine pages.

11. If HEALED:
    - Loop prepares draft upstream report as .kiro/specs/<routine>/<routine>.upstream.draft.txt.
    - Human reviews and decides whether to file or discard.
```

## Enforcement of Requirements

| Requirement | Enforced By | Mechanism |
|-------------|-------------|-----------|
| 1. Inherited flaws (DLNGAM, DGAMR link to healed DGAMMA) | harness.trial during linking | Oracle maps routine to its callees; if callee is healed, substitute port in link step. |
| 2. Cold test integrity (loop frozen, exam protected, credit cap, stop on 2 fails) | harness.loop + guard hooks | Loop checks git tag at entry; guard blocks writes to harness/, oracle/, tests/; loop enforces credit counter and failed-round counter. |
| 3. Held-out trial gate for HEALED | harness.loop (outside agent context) | Loop schedules held-out trial only after RESURRECTED; agent never sees those inputs; result gated at verdict time. |
| 4. Honest reporting (all verdicts logged with equal prominence) | harness.transcription + site/tools/build.py | Transcription writes verdict, pass rates, ULP stats, credits to JSON; site builder renders all verdicts with same visibility and metadata. |
| 5. Upstream draft (prepared, not filed automatically) | harness.loop after HEALED gate passes | Loop writes .upstream.draft.txt; no automated filing. |
| 6. Credit cap and stop rule (max 1.5 credits, stop on 2 failed rounds) | harness.loop iteration counter | Loop maintains credit and failed-round counters; exits when either limit is hit. |
| 7. Flaw Ledger integrity (only measured values) | harness.transcription + site/tools/build.py | Only committed run JSON files contribute to ledger; numbers come from trial output, never hand-typed. |

## Error Handling

### 429 Throttling (Open Design Question)
If the Kiro API returns 429 (rate limit):
- Log the error with timestamp and attempt count.
- Retry is an open design question: how many retries? what delay? what stop reason if all fail?
- Current behavior should be recorded in stop reason and run JSON.

### Timeouts (Open Design Question)
If a trial or agent call exceeds 15 minutes:
- Log timeout with routine name and round number.
- Timeout is an open design question: stop immediately with reason "timeout" and mark VOID? Retry? Credit handling?
- Current behavior should be recorded in stop reason and run JSON.

### VOID Exam (exam files changed during the round)
If `git diff loop-frozen-1 -- harness oracle tests fortran tools .kiro/steering .kiro/agents .kiro/hooks` is not empty:
- Preflight: loop exits with VOID, no run JSON written.
- Per-trial check: trial marked VOID, loop exits.
- Run JSON records stop reason "exam files changed during the round".

### AST Violations (DISQUALIFIED)
If harness.port_guard detects non-math imports, open/exec/eval/__import__/compile/globals, or dunder attributes:
- harness.trial's AST check (before import) rejects the port.
- Trial returns DISQUALIFIED.
- Loop marks routine as DISQUALIFIED, exits.

### Missing Routine
If a routine is not in the list of flawed originals (DPSI, DLNGAM, DGAMR):
- Loop logs error and exits without creating a run JSON.

## Correctness Properties

### Property 1: ULP Metric Consistency
**Claim:** ULP values in run JSON match the definition in verification_rules.md.
**Validation:** harness/tests/ includes unit tests for ULP computation (ulp_matches_ref, ulp_subnormal_handling). These tests verify the formula `ulp(x) = |got - ref| / spacing(|ref|)` and special cases (ref=0, NaN, Inf, subnormal).

### Property 2: Verdict Derivation
**Claim:** A verdict (RESURRECTED, UNDEAD, STILL DEAD, HEALED) is derived correctly from pass_rate.
**Validation:** harness/tests/ includes tests for verdict_from_pass_rates that check:
- RESURRECTED: port pass_rate ≥ 99.0 % on all sub-domains (original pass_rate irrelevant).
- HEALED: RESURRECTED AND held-out trial also RESURRECTED AND original pass_rate < 95.0 % on ≥ 1 sub-domain.
- UNDEAD: port pass_rate ≥ 90.0 % on all sub-domains but not RESURRECTED.
- STILL DEAD: port pass_rate < 90.0 % on any sub-domain, or DISQUALIFIED, or crash.

### Property 3: Loop Termination
**Claim:** The loop terminates in finite time and respects the credit cap (default 1.5).
**Validation:** Loop enforces:
- Credit counter starts at 0; increments by 0.75 per dev trial.
- Failed-round counter starts at 0; increments on UNDEAD or STILL DEAD.
- Exit when failed-round counter ≥ 2 (stop reason "two_failed_rounds_in_a_row").
- Exit when spent + estimate > credit_cap (stop reason "credit_cap (...)").
- Held-out trials do not count against budget.
- Timeout on any single call (15 minutes; stop reason "timeout", marked VOID).

### Property 4: AST Safety
**Claim:** No port imports anything other than `math`; no disallowed builtins are used.
**Validation:** harness/trial.py's AST check (before import) walks the parse tree and rejects:
- Any `import` or `from ... import` statement other than `math`.
- Any call to `open`, `exec`, `eval`, `__import__`, `compile`, `globals`.
- Any dunder attribute access (e.g., `obj.__dict__`).
- If any check fails, trial returns DISQUALIFIED immediately.

### Property 5: Exam Integrity
**Claim:** Run JSON includes the git commit hash; loop verifies exam files are unchanged from loop-frozen-1.
**Validation:** harness.transcription reads `git rev-parse HEAD` and includes the SHA in the JSON. Loop checks `git diff loop-frozen-1 -- harness oracle tests fortran tools .kiro/steering .kiro/agents .kiro/hooks` at entry; if not empty, outputs VOID (stop reason "exam files changed during the round"). Per-trial check repeats this; if violated, trial marked VOID.

## Data Schema (Run JSON)

```json
{
  "name": "<routine>",
  "model": "<model>",
  "run_id": "<timestamp>",
  "max_rounds": <int>,
  "credit_cap": <float>,
  "dev": {
    "seed": <int>,
    "n": <int>
  },
  "heldout": {
    "seed": <int>,
    "n": <int>,
    "verdict": "<verdict>",
    "file": "<path_to_json>"
  },
  "start_commit": "<sha>",
  "rounds": [
    {
      "round": <int>,
      "pass_rates": {
        "overall": <float>,
        "<subdomain>": <float>
      },
      "max_ulp": {
        "overall": <float>,
        "<subdomain>": <float>
      },
      "median_ulp": {
        "overall": <float>,
        "<subdomain>": <float>
      },
      "p99_ulp": {
        "overall": <float>,
        "<subdomain>": <float>
      },
      "worst_x": {
        "<subdomain>": <float>
      }
    }
  ],
  "total_credits": <float>,
  "stop_reason": "<reason_or_null>",
  "result": "<verdict>"
}
```

Top-level keys: `name`, `model`, `run_id`, `max_rounds`, `credit_cap`, `dev`, `heldout`, `start_commit`, `rounds[]`, `total_credits`, `stop_reason`, `result`.

Example STILL DEAD:
```json
{
  "name": "dpsi",
  "model": "claude-haiku-4.5",
  "run_id": "<timestamp>",
  "credit_cap": 1.5,
  "dev": { "seed": <int>, "n": <int> },
  "heldout": null,
  "start_commit": "<sha>",
  "total_credits": 1.5,
  "stop_reason": "two_failed_rounds_in_a_row",
  "result": "STILL DEAD"
}
```

Example HEALED:
```json
{
  "name": "dgamma",
  "model": "claude-haiku-4.5",
  "run_id": "<timestamp>",
  "credit_cap": 1.5,
  "dev": { "seed": <int>, "n": <int> },
  "heldout": {
    "seed": 7,
    "n": 10000,
    "verdict": "RESURRECTED",
    "file": "<path>"
  },
  "start_commit": "<sha>",
  "total_credits": 0.75,
  "stop_reason": null,
  "result": "HEALED"
}
```
