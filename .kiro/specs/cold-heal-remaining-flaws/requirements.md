# Cold Test of Remaining Flawed Originals – Requirements

## Overview

This feature runs honest cold tests on the remaining SLATEC FNLIB originals that fail at least one input range: DPSI (small 13.5%, negative 51.3%), DLNGAM and DGAMR (which call DGAMMA and inherit its flaws). DERF is out of scope (Maxima bug 2491, known upstream since 2012). Each cold test runs with the exam frozen (harness/, oracle/, tests/, fortran/, tools/, .kiro/steering/, .kiro/agents/, .kiro/hooks/ unchanged from tag loop-frozen-1) with a maximum of 1.5 credits per routine and a stop rule after two failed rounds. All outcomes—HEALED, UNDEAD, and STILL DEAD—are logged and reported on the ledger and site with equal prominence.

## Requirement 1: Inherited Flaws (DLNGAM, DGAMR)

**User Story:** As a verification engineer, I want a Python port of DLNGAM and DGAMR that calls Kiro's healed routines/dgamma.py, so that I can measure whether they pass with the fixed DGAMMA.

**Acceptance Criteria:**
1.1. A port of DLNGAM exists in routines/dlngam.py that calls routines.dgamma() instead of external DGAMMA.
1.2. A port of DGAMR exists in routines/dgamr.py that calls routines.dgamma() instead of external DGAMMA.
1.3. When DLNGAM or DGAMR trial completes, the pass_rate for each sub-domain is recorded in the run JSON with the inherited DGAMMA port's pass rate.

## Requirement 2: Cold Test Integrity

**User Story:** As a project auditor, I want confirmation that the exam is locked during these runs, so that I can trust the results are truly cold tests on unseen inputs.

**Acceptance Criteria:**
2.1. When the loop begins, it verifies `git diff loop-frozen-1 -- harness oracle tests fortran tools .kiro/steering .kiro/agents .kiro/hooks` is empty; if not, the run is marked VOID (stop reason "exam files changed during the round").
2.2. During loop execution, if any trial detects changes to protected files, that trial is marked VOID and the loop exits.
2.3. When a routine completes two consecutive failed rounds (each returning UNDEAD or STILL DEAD), the loop stops further rounds and records stop reason "two_failed_rounds_in_a_row".

## Requirement 3: Held-Out Trial Gate for HEALED

**User Story:** As a result validator, I want HEALED verdicts to require both a dev trial and a held-out trial, so that the agent never sees held-out inputs and I can be certain a port is truly fixed.

**Acceptance Criteria:**
3.1. When a routine's port returns RESURRECTED on the dev trial, a held-out trial (seed 7, 10,000 inputs) is launched outside the agent's view.
3.2. The held-out trial result is recorded in the run JSON under `heldout` with keys `seed`, `n`, `verdict`, and `file`.
3.3. A verdict of HEALED requires: port pass_rate ≥ 99.0% on every dev sub-domain AND held-out pass_rate ≥ 99.0% on every sub-domain AND original pass_rate < 95.0% on at least one sub-domain.
3.4. If held-out verdict is UNDEAD or STILL DEAD, the routine is marked with that verdict, not HEALED.

## Requirement 4: Honest Reporting

**User Story:** As a project stakeholder, I want all outcomes—HEALED, UNDEAD, and STILL DEAD—recorded on the ledger and site with the same prominence and full metadata, so that I can audit success and failure equally.

**Acceptance Criteria:**
4.1. Run JSON is saved to runs/ledger/<routine>_<run_id>.json with keys: `name`, `model`, `run_id`, `max_rounds`, `credit_cap`, `dev` {seed, n}, `heldout` {seed, n, verdict, file}, `start_commit`, `rounds[]`, `total_credits`, `stop_reason`, `result`.
4.2. Each round in `rounds[]` includes pass_rate, max_ulp, median_ulp, p99_ulp, worst_x per sub-domain.
4.3. STILL DEAD and UNDEAD verdicts are displayed on the site with the same text prominence as HEALED, including all trial metadata, credits spent, and stop reason.
4.4. The ledger page lists all entries (HEALED, UNDEAD, STILL DEAD, VOID) sorted by routine name and trial timestamp.

## Requirement 5: Upstream Report Draft

**User Story:** As a maintainer preparing a bug report, I want a draft upstream report prepared for each HEALED flaw, so that I can review it and decide whether to file a formal issue.

**Acceptance Criteria:**
5.1. When a routine achieves HEALED status, a plaintext draft is prepared and saved to `.kiro/specs/<routine>/<routine>.upstream.draft.txt`.
5.2. The draft includes: routine name, failing input range, one-line description of the fix, and trial run identifiers (seed, size, pass rates).
5.3. The draft is not filed automatically; a human reviews and decides whether to submit.

## Requirement 6: Per-Routine Credit Cap and Stop Rule

**User Story:** As a resource manager, I want each cold test to spend at most 1.5 credits (default --credit-cap) and stop after two consecutive failed rounds, so that we conserve model calls on routines that are not converging.

**Acceptance Criteria:**
6.1. Loop initializes credit counter at 0 and failed-round counter at 0 per routine.
6.2. Each completed dev trial charges 0.75 credits (two rounds = 1.5 max).
6.3. Each UNDEAD or STILL DEAD round increments failed-round counter by 1.
6.4. When failed-round counter reaches 2, loop stops further rounds and records stop reason "two_failed_rounds_in_a_row".
6.5. Before starting a round, if `spent + estimate > credit_cap`, loop exits with stop reason "credit_cap (...)".
6.6. Held-out trials do not count against the credit cap.

## Requirement 7: Flaw Ledger Integrity

**User Story:** As an auditor, I want the Flaw Ledger to contain only flaws measured by the pipeline, so that I can rely on every number in it.

**Acceptance Criteria:**
7.1. The Flaw Ledger is built only from committed run JSON files under runs/ledger/.
7.2. Each ledger entry references the run JSON filename and the git commit hash (recorded at trial time).
7.3. No speculative or hand-typed numbers are added; all data come from trial output JSON.
