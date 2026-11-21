# Cold Test of Remaining Flawed Originals – Design

## Component Overview

The cold test feature integrates the following existing components:

- **harness.loop**: Orchestrates rounds of agent edits and trials; runs one command per routine.
- **harness.trial**: Runs the exam (original Fortran + port + mpmath referee) on a given routine and sub-domain range, outputs JSON with pass rates, ULP stats, and verdict.
- **harness.autopsy**: Analyzes a failed trial to suggest which input range or code line failed and why.
- **harness.transcription**: Logs trial metadata (toolchain, git commit, manifest hash) into run JSON.
- **resurrector agent**: Receives autopsy hints; edits routines/<name>.py to fix failing cases; calls Kiro CLI to trigger trial re-run.
- **guard hooks** (.kiro/hooks): Block reads/writes to protected files; enforce VOID on exam changes.
- **site/tools/build.py**: Reads run JSON files and renders the ledger and routine pages.

## Data Flow of One Cold Test Round

```
1. User invokes: python -m harness.loop <routine> --model claude-haiku-4.5

2. Loop checks:
   - Git commit == loop-frozen-1 tag? If not, output VOID, exit.
   - Routine in list of flawed originals (DPSI, DLNGAM, DGAMR)? If not, error.

3. Trial execution (harness.trial):
   - Compile Fortran original.
   - Compile/import Python port from routines/<routine>.py.
   - For each sub-domain (tiny, small, negative, etc.):
     a. Generate test inputs (via hypothesis or fixed seed).
     b. Call Fortran original, Python port, mpmath referee on each input.
     c. Compute ULP(x) for each input; check pass(x) = ulp(x) <= allowed(x).
     d. Record pass_rate, max_ulp, median_ulp, p99_ulp, worst_x.
   - Aggregate across sub-domains; determine verdict (RESURRECTED, UNDEAD, STILL DEAD).
   - Write run JSON with all stats and verdict.

4. Transcription (harness.transcription):
   - Append toolchain (gfortran version, Python, numpy, mpmath versions) to run JSON.
   - Append git commit hash of repo at trial time.
   - Append sha256 manifest of harness/, oracle/, and routines/<routine>.py.

5. Verdict check:
   - IF verdict == STILL DEAD or UNDEAD:
     a. Charge 0.75 credits; increment failed-round counter.
     b. IF failed-round counter >= 2: skip further rounds, write stop reason, exit.
     c. ELSE: invoke autopsy.
   - IF verdict == RESURRECTED:
     a. Charge 0.75 credits; increment success counter.
     b. Schedule held-out trial (outside agent view) with seed 7, 10,000 inputs.
     c. If held-out trial also RESURRECTED: mark HEALED in ledger, prepare upstream draft.
     d. If held-out trial UNDEAD or STILL DEAD: mark UNDEAD/STILL DEAD in ledger.
     e. Exit (do not continue rounds).

6. Autopsy (if continuing):
   - harness.autopsy reads run JSON; identifies sub-domain and input(s) that failed worst.
   - Computes autopsy hints: "input X in tiny range failed by Y ULP", "x + i - 1 line likely", etc.
   - Outputs hint text to stdout or log.

7. Agent invocation (if continuing and credits < 1.5):
   - Loop writes autopsy hints to a temp file.
   - Invokes: kiro-cli agent run --path .kiro/agents/resurrector.json --args "routine=<name> hints=<file>"
   - Agent reads fortran/slatec/<routine>.f, routines/<routine>.py, and hints.
   - Agent edits routines/<routine>.py to fix the failing case(s).
   - Agent returns; loop checks for AST violations (imports, disallowed builtins).
   - If AST clean: loop goes to step 3 (new trial). Else: DISQUALIFIED, exit.

8. Loop output:
   - Write final run JSON (with all round histories and final verdict) to runs/ledger/<routine>_<timestamp>.json.
   - Commit run JSON to git (if not VOID).
   - Optionally invoke site/tools/build.py to update site HTML.

9. If HEALED, loop also:
   - Prepares short upstream draft (routine, range, fix, trials) as .kiro/specs/<routine>/<routine>.upstream.draft.txt.
   - Logs to stdout: "HEALED: <routine>, ready for upstream review."
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

### 429 Throttling
If the Kiro API returns 429 (rate limit), the loop SHALL:
- Log the error with timestamp.
- Wait 30 seconds (or per Kiro guidance).
- Retry the agent invocation up to 3 times.
- If 3 retries fail: mark routine as VOID with reason "API throttling", exit.

### Timeouts
If a trial or agent call exceeds 15 minutes:
- Log timeout with routine name and round number.
- Mark routine as VOID with reason "timeout", exit.
- Do not retry.

### VOID Exam
If guard hooks detect writes to harness/, oracle/, or tests/ during a run:
- Mark run as VOID with reason "exam modified".
- Write VOID to run JSON and commit.
- Do not execute further rounds on that routine.

### AST Violations
If the resurrected agent's code edit imports non-math modules or uses disallowed builtins:
- harness.trial's AST check (before import) rejects the import.
- Trial returns DISQUALIFIED.
- Loop marks routine as DISQUALIFIED, exits.

### Missing Input Range
If a routine is not in the list of flawed originals (DPSI, DLNGAM, DGAMR) or the range string is invalid:
- Loop logs error and exits immediately without creating a run JSON.

## Correctness Properties

### Property 1: ULP Metric Consistency
**Claim:** ULP values in run JSON match the definition in verification_rules.md.
**Validation:** harness/tests/ includes unit tests for ULP computation (ulp_matches_ref, ulp_subnormal_handling). These tests verify the formula `ulp(x) = |got - ref| / spacing(|ref|)` and special cases (ref=0, NaN, Inf, subnormal).

### Property 2: Verdict Derivation
**Claim:** A verdict (RESURRECTED, UNDEAD, STILL DEAD, HEALED) is derived correctly from pass_rate.
**Validation:** harness/tests/ includes tests for verdict_from_pass_rates that check:
- RESURRECTED: pass_rate ≥ 99.0 % on all sub-domains AND original pass_rate < 95.0 % on ≥ 1 sub-domain.
- UNDEAD: pass_rate ≥ 90.0 % on all sub-domains but not RESURRECTED.
- STILL DEAD: pass_rate < 90.0 % on any sub-domain.
- HEALED: RESURRECTED AND held-out trial also RESURRECTED AND original pass_rate < 95.0 % on ≥ 1 sub-domain.

### Property 3: Loop Termination
**Claim:** The loop terminates in finite time and respects the credit cap.
**Validation:** Loop enforces:
- Maximum 2 rounds per routine (credits = 0.75 + 0.75 = 1.5 max).
- Exit after 2 consecutive failed rounds (UNDEAD or STILL DEAD).
- Exit on RESURRECTED (held-out trial runs in parallel, not counted against loop budget).
- Timeout on any single round (15 minutes).

### Property 4: AST Safety
**Claim:** No port imports anything other than `math`; no disallowed builtins are used.
**Validation:** harness/trial.py's AST check (before import) walks the parse tree and rejects:
- Any `import` or `from ... import` statement other than `math`.
- Any call to `open`, `exec`, `eval`, `__import__`, `compile`, `globals`.
- Any dunder attribute access (e.g., `obj.__dict__`).
- If any check fails, trial returns DISQUALIFIED immediately.

### Property 5: Git Integrity
**Claim:** Run JSON includes the git commit hash; loop verifies the repo is at loop-frozen-1 at entry.
**Validation:** harness.transcription reads `git rev-parse HEAD` and includes the SHA in the JSON. Loop checks `git rev-list -n 1 loop-frozen-1` at entry and compares; if mismatch, outputs VOID.

## Data Schema (Run JSON)

```json
{
  "routine": "dpsi",
  "verdict": "UNDEAD",
  "credits_spent": 1.5,
  "stop_reason": "two failed rounds",
  "rounds": [
    {
      "round": 1,
      "trial_type": "dev",
      "pass_rates": {
        "overall": 68.5,
        "small": 13.5,
        "negative": 51.3
      },
      "max_ulp": { "overall": 1200.5, "small": 2000.3, "negative": 1500.2 },
      "median_ulp": { "overall": 50.2, "small": 150.3, "negative": 80.1 },
      "worst_x": { "small": 1.2345e-10 }
    },
    {
      "round": 2,
      "trial_type": "dev",
      "pass_rates": { "overall": 69.2, "small": 14.1, "negative": 52.0 },
      "max_ulp": { "overall": 1150.3, "small": 1950.2, "negative": 1480.1 },
      "median_ulp": { "overall": 49.8, "small": 148.5, "negative": 78.9 },
      "worst_x": { "small": 1.3456e-10 }
    }
  ],
  "toolchain": {
    "gfortran_version": "GCC 16.x",
    "python_version": "3.11.x",
    "numpy_version": "1.26.x",
    "mpmath_version": "1.4.1",
    "scipy_version": "1.14.x"
  },
  "git_commit": "abc123def456...",
  "manifest_sha256": "sha256_of_harness_oracle_routine_files",
  "timestamp": "2026-11-17T20:30:45Z"
}
```

If HEALED:

```json
{
  "routine": "dcot",
  "verdict": "HEALED",
  "credits_spent": 0.75,
  "stop_reason": null,
  "rounds": [
    {
      "round": 1,
      "trial_type": "dev",
      "pass_rates": { "overall": 99.5, "near_pi": 99.8 }
    }
  ],
  "held_out_trial": {
    "seed": 7,
    "n_inputs": 10000,
    "pass_rates": { "overall": 99.2, "near_pi": 99.1 },
    "verdict": "RESURRECTED"
  },
  "upstream_draft_file": ".kiro/specs/dcot/dcot.upstream.draft.txt"
}
```
