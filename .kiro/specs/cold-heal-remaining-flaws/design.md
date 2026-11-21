# Cold-heal the remaining flawed originals: design

## What already exists (at tag loop-frozen-1)

| Part | File | What it does |
|---|---|---|
| Loop | harness/loop.py | One command: blind port if needed, dev trial, evidence, Kiro repair, verbatim commit, dev trial again; undo rounds that hurt or don't help; held-out gate; ledger |
| Trial | harness/trial.py | Runs the port (in its own process, harness/port_runner.py) and the compiled original on the same seeded inputs (oracle/referees.make_inputs) against the 50-digit referee; records per-range pass_rate, max/median/p99 ULP, worst_x, toolchain, git commit and a sha256 manifest of the exam |
| Verdict | harness/verdict.py | RESURRECTED / HEALED / UNDEAD / STILL DEAD / DISQUALIFIED from per-range pass rates |
| Import guard | harness/port_guard.py | AST check before import: only `math`; no open/exec/eval/__import__/compile/globals; no dunder attributes; else DISQUALIFIED |
| Feedback | harness/feedback.py | The plain-text trial report the agent sees (never a fix) |
| Autopsy | harness/autopsy.py | Runs the port in double and in 60-digit shadow arithmetic, line by line, and names the first line and operation where digits are lost |
| Constant check | harness/transcription.py | Compares every numeric DATA constant in the Fortran with the port's copy (added after the DCOT blind port mistyped two Chebyshev coefficients) |
| Ablation | harness/ablate.py | Splits a repair into hunks and trials each hunk on its own |
| Agent | .kiro/agents/resurrector.json | Tools: read, write. May write only routines/** and .kiro/specs/**. PreToolUse allowlist guard (tools/guard/allowlist_guard.py, exit 2 = block, fails closed) and a Stop hook that runs git diff on the exam |
| Workspace hook | .kiro/hooks/save-log | PostFileSave: logs every saved file to runs/guard_log/ (git-ignored) |
| Site | site/tools/build.py | Static site from committed runs only; census, flaw cards, in-browser re-run (Pyodide); browser test site/tools/test_site.py |

The agent is called as
`kiro-cli chat --v3 --no-interactive --trust-all-tools --agent resurrector --model {model} --output-format stream-json "<prompt>"`
(DEFAULT_AGENT_CMD in harness/loop.py). The agent cannot run trials; the loop runs them outside its session.

## One round

```
loop(name, model="claude-haiku-4.5", max_rounds=4, credit_cap=1.5)
  preflight: exam paths clean in git (else error "exam_dirty"); routines/<name>.py clean
  if no port: blind port by Kiro -> verbatim commit (round 0, type "port")
  dev trial (seed 1, n 2000)
  for k in 1..max_rounds:
      stop if trial is VOID or DISQUALIFIED
      stop if total_credits + estimate > credit_cap            # estimate = dearest call so far, or 0.5
      prompt = trial report + autopsy of worst inputs + constant check + last round's ablation + own diffs
      call Kiro (retry 30 s, 90 s on 429 / timeout 900 s / non-zero exit, never after the port changed)
      stop "exam files changed during the round" if an exam path changed
      commit the agent's change verbatim, with the prompt next to it
      overfit guard -> undo ("rejected") | dev trial ->
          worse in any range  -> undo with a new commit ("reverted")
          no range improved   -> undo ("no_gain")
          else keep ("repair")
      stop "two_failed_rounds_in_a_row" after two undone rounds in a row
  if the dev trial succeeded: held-out trial (seed 7, n 10000, never shown to the agent)
      agrees -> result = verdict, stop "<verdict>_confirmed"; else stop "heldout_disagrees"
  write and commit runs/ledger/<name>_<run_id>.json
```

## Where each requirement is enforced

| Req | Where | Status |
|---|---|---|
| 1.1 DLNGAM/DGAMR call the healed DGAMMA | port prompt + routines/ (the agent may import from routines/) | to check: port_guard allows only `math` imports, so the port must inline or copy dgamma, or the guard needs a `routines.*` exception. Decide before task 3. |
| 1.2 per-range port and original results | harness/trial.py | done |
| 1.3 ledger note for inherited passes | site/tools/build.py CENSUS_NOTES + ledger note | to do |
| 2.1 frozen diff empty | a check run before each cold run (task 1) | to do (one command, recorded in the run notes) |
| 2.2 preflight | harness/loop.py exam_dirty() | done |
| 2.3 change during a round | harness/loop.py guard_breach | done |
| 2.4 agent sees no exam | resurrector.json + allowlist_guard.py + feedback.py | done (cheat probe: 4 of 4 attempts blocked) |
| 3.x held-out gate | harness/loop.py | done |
| 4.1, 4.2 ledger | harness/loop.py | done |
| 4.3, 4.4 site | site/tools/build.py | check after each run |
| 5.x upstream drafts | written by the resurrector into .kiro/specs/ | to do |
| 6.x credits and stops | harness/loop.py, harness/kiro_session.py | done |

## Error handling

- 429 and timeouts: three attempts with 30 s and 90 s waits; the 900 s timeout is per call. Credits from failed
  attempts are still added (they were spent). After the third failure: stop "agent_error".
- A failed blind port: stop "port_failed", commit what was written.
- VOID trial (exam dirty at trial time): stop "trial_void".
- DISQUALIFIED port: stop "trial_disqualified"; the port stays in git so the reason can be read.

## Correctness properties

Each property is checked by a test that runs today (91 tests in tests/).

- P1 ULP metric matches verification_rules.md, including zero, NaN, Inf and subnormal cases:
  tests/test_harness.py test_ulp_*.
- P2 Verdict rules (RESURRECTED needs >= 99.0% everywhere; HEALED also needs the original < 95.0% somewhere;
  UNDEAD >= 90.0% everywhere; STILL DEAD otherwise; DISQUALIFIED on a guard failure):
  tests/test_harness.py test_verdict_*.
- P3 Only `math` may be imported, no open/exec/dunder: tests/test_harness.py test_guard_*.
- P4 The agent cannot write or read the exam, including through shell tools, path traversal or a malformed hook
  input (fails closed): tests/test_guard.py (30 tests).
- P5 Loop stops: heals and confirms on held-out, held-out disagreement is not a success, two undone rounds stop
  the loop, the credit cap stops before overspending, no diff twice stops, a throttle is retried, an agent
  writing outside routines/ stops the loop, a dirty exam is refused: tests/test_loop.py (17 tests, using a fake
  agent).
- P6 Every round that makes a range worse is undone by a new commit, never by rewriting history:
  tests/test_loop.py test_two_changes_one_bad_is_undone_with_a_new_commit.
- P7 Prompts never carry a fix hint: tests/test_loop.py test_prompts_carry_no_fix_hint.

## Ledger file shape

```json
{
  "name": "<routine>", "model": "<model>", "run_id": "<UTC timestamp>",
  "max_rounds": <int>, "credit_cap": <float>,
  "dev": {"seed": 1, "n": 2000},
  "heldout": {"seed": 7, "n": 10000, "verdict": "<verdict, only if run>", "file": "<runs/... json, only if run>"},
  "start_commit": "<sha>",
  "rounds": [{"round": <int>, "type": "port|repair|reverted|no_gain|rejected|...", "commit": "<sha>",
              "credits": <float>, "trial_before": "<summary>", "trial_after": "<summary>",
              "undo_commit": "<sha, if undone>"}],
  "total_credits": <float>, "stop_reason": "<reason>", "result": "<verdict or null>"
}
```
