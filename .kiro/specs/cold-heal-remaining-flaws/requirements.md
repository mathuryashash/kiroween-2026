# Cold-heal the remaining flawed originals: requirements

## Introduction

The census (runs/census/census_20261117T185024Z.json and census_20261117T185719Z.json, 36 SLATEC FNLIB originals,
n = 1000, seed 11) found six originals that fail at least one input range:

| Routine | Failing range (census) | Status |
|---|---|---|
| DGAMMA | tiny 0.0% | HEALED by Kiro, confirmed on held-out seed 7, n 10000 (f933cca) |
| DCOT | near_pi 70.5% | HEALED by Kiro (loop run 20261117T193644Z, 0.25 credits, tag loop-frozen-1). Not a cold test: the loop was tuned during DCOT. |
| DPSI | small 13.5%, negative 51.3% | STILL DEAD after the first cold run (loop run 20261117T193921Z, 0.93 credits, ba04301) |
| DLNGAM | tiny 0.0% | calls DGAMMA; passes when linked to the fixed Fortran DGAMMA (census 185719Z) |
| DGAMR | small 11.1% | calls DGAMMA; passes when linked to the fixed Fortran DGAMMA (census 185719Z) |
| DERF | tiny 58.5% | out of scope: the flaw is already known upstream (Maxima bug 2491, 2012) |

This feature runs the frozen one-command loop (`python -m harness.loop <name> --model claude-haiku-4.5 --credit-cap 1.5`)
as honest cold tests on DPSI, DLNGAM and DGAMR, and reports every outcome, good or bad.

"Frozen" means `git diff loop-frozen-1 -- harness oracle tests fortran tools .kiro/steering .kiro/agents .kiro/hooks`
is empty. Commits to routines/, runs/, site/ and .kiro/specs/ after the tag are expected and do not break the freeze.

## Requirement 1: Inherited flaws (DLNGAM, DGAMR)

**User story:** As a verification engineer, I want Python ports of DLNGAM and DGAMR that call Kiro's healed
routines/dgamma.py, so that I can see whether the inherited failure disappears in Python too, not only in the
fixed Fortran.

**Acceptance criteria**
- 1.1 WHEN the loop ports DLNGAM or DGAMR, THE SYSTEM SHALL let the port call `dgamma` from routines/dgamma.py
  (the HEALED port at f933cca) instead of re-porting DGAMMA.
- 1.2 WHEN the trial of a DLNGAM or DGAMR port finishes, THE SYSTEM SHALL record per-range pass rates for the port
  and for the compiled original on the same inputs, as for every other port.
- 1.3 IF a DLNGAM or DGAMR port passes only because of the healed DGAMMA, THEN THE SYSTEM SHALL say so in the
  ledger note, so the result is not counted as a new heal.

## Requirement 2: Cold-test integrity

**User story:** As an auditor, I want proof that nothing in the exam changed during these runs, so that the
results count as cold tests.

**Acceptance criteria**
- 2.1 WHEN a cold run is started, THE SYSTEM SHALL first show that the frozen diff (see Introduction) is empty.
  IF it is not empty, THEN the run SHALL NOT be reported as a cold test.
- 2.2 WHEN the loop starts, THE SYSTEM SHALL refuse to run if any exam path has uncommitted changes
  (harness/loop.py preflight, error "exam_dirty").
- 2.3 WHILE the loop runs, IF an exam path changes during a round, THEN THE SYSTEM SHALL stop with stop reason
  "exam files changed during the round: ..." and the trial verdict SHALL be VOID.
- 2.4 THE SYSTEM SHALL never show the agent the held-out inputs, the referee values outside the feedback report,
  or anything under harness/, oracle/, tests/ or runs/.

## Requirement 3: Held-out gate for HEALED

**User story:** As a reviewer, I want a heal to count only when inputs the agent never saw agree, so that a port
cannot pass by fitting the dev inputs.

**Acceptance criteria**
- 3.1 WHEN the dev trial (seed 1, n 2000) succeeds, THE SYSTEM SHALL run the held-out trial (seed 7, n 10000)
  outside the agent's session.
- 3.2 THE SYSTEM SHALL record the held-out result in the ledger under `heldout` with `seed`, `n`, `verdict` and `file`.
- 3.3 IF the held-out trial also succeeds, THEN THE SYSTEM SHALL set `result` to the held-out verdict and stop with
  "<verdict>_confirmed". HEALED itself means: port pass_rate >= 99.0% on every range AND the original's
  pass_rate < 95.0% on at least one range (harness/verdict.py).
- 3.4 IF the held-out trial does not succeed, THEN THE SYSTEM SHALL stop with "heldout_disagrees" and SHALL NOT
  report the routine as healed.

## Requirement 4: Honest reporting

**User story:** As a judge or reader, I want failures shown as clearly as wins, so that I can trust the wins.

**Acceptance criteria**
- 4.1 WHEN a loop run ends, THE SYSTEM SHALL write runs/ledger/<name>_<run_id>.json with the keys `name`, `model`,
  `run_id`, `max_rounds`, `credit_cap`, `dev`, `heldout`, `start_commit`, `rounds`, `total_credits`,
  `stop_reason`, `result`, and commit it.
- 4.2 THE SYSTEM SHALL record, for every round, its type (port, repair, reverted, no_gain, rejected), the credits
  Kiro reported, the commit of the agent's verbatim change, the undo commit if any, and the trial result before
  and after.
- 4.3 WHEN the site is built, THE SYSTEM SHALL show every cold-test outcome (HEALED, UNDEAD, STILL DEAD, VOID) with
  its credits and stop reason, using the same card layout as HEALED routines.
- 4.4 THE SYSTEM SHALL take every number on the site from a committed run file and link to it.

## Requirement 5: Upstream report drafts

**User story:** As the maintainer of this project, I want a short draft report for each confirmed flaw, so that
I can decide whether to file it with the maintained SLATEC forks.

**Acceptance criteria**
- 5.1 WHEN a routine is HEALED and confirmed, THE SYSTEM SHALL produce a draft at
  .kiro/specs/cold-heal-remaining-flaws/upstream/<name>.md with: routine, failing range, the original line, the
  one-line fix, and the dev and held-out pass rates with their run files.
- 5.2 THE SYSTEM SHALL NOT file anything upstream. A person reads the draft and decides.

## Requirement 6: Credit cap and stop rules

**User story:** As the person paying for the credits, I want each cold run to stop early when it isn't working.

**Acceptance criteria**
- 6.1 THE SYSTEM SHALL read the real credits of every Kiro call from the stream JSON
  (harness/kiro_session.py) and add them to `total_credits`.
- 6.2 WHEN a round is about to start, IF `total_credits` + the estimate (the most expensive call so far, or 0.5
  before the first call) would exceed `--credit-cap`, THEN THE SYSTEM SHALL stop with "credit_cap (...)".
  Cold runs use `--credit-cap 1.5`.
- 6.3 WHEN two rounds in a row are undone (reverted, no_gain or rejected), THE SYSTEM SHALL stop with
  "two_failed_rounds_in_a_row".
- 6.4 WHEN the agent produces no change twice, THE SYSTEM SHALL stop with "no_diff_twice".
- 6.5 IF a Kiro call is throttled (429), times out (900 s) or exits non-zero, THEN THE SYSTEM SHALL retry after
  30 s and then 90 s, but never after the agent has already changed the port. IF all three attempts fail, THEN it
  SHALL stop with "agent_error" and keep the credits already spent in the ledger.
