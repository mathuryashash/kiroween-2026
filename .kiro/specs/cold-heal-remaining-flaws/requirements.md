# Cold Test of Remaining Flawed Originals – Requirements

## Overview

This feature runs honest cold tests on the remaining SLATEC FNLIB originals that fail at least one input range: DPSI (small 13.5%, negative 51.3%), DLNGAM and DGAMR (which call DGAMMA and inherit its flaws). Each cold test runs the frozen loop code (locked at tag loop-frozen-1) with a maximum of 1.5 credits per routine and a stop rule after two failed rounds. All outcomes—HEALED, UNDEAD, and STILL DEAD—are logged and reported on the ledger and site with equal prominence.

## Requirement 1: Inherited Flaws (DLNGAM, DGAMR)

**User Story:** As a verification engineer, I want routines that call DGAMMA to inherit the healed DGAMMA port automatically during trial, so that I can measure whether the inherited failure disappears without manual agent edits.

**Acceptance Criteria:**
- WHEN DLNGAM or DGAMR is linked against the original Fortran during trial, THE SYSTEM SHALL substitute the healed DGAMMA port in its place without requiring agent code changes.
- IF DLNGAM or DGAMR trial completes, THEN the pass_rate for each sub-domain SHALL be recorded in the run JSON.
- IF the inherited flaw disappears (all sub-domains pass_rate ≥ 95%), THEN the verdict SHALL reflect the healed DGAMMA port's pass rate, not the original DGAMMA.

## Requirement 2: Cold Test Integrity

**User Story:** As a project auditor, I want confirmation that the loop code and exam are locked from the frozen tag during these runs, so that I can trust the results are truly cold tests on unseen inputs.

**Acceptance Criteria:**
- WHEN the loop begins, THE SYSTEM SHALL verify that the git commit equals tag loop-frozen-1, or the run SHALL be marked VOID and stopped immediately.
- WHILE the loop runs, THE SYSTEM SHALL not apply any edits to loop.py, harness/, or oracle/.
- IF a VOID condition is detected, THEN the run JSON SHALL record VOID with the reason and zero credits assigned.
- WHEN a routine completes two rounds of failures in a row (each round returning UNDEAD or STILL DEAD), THE SYSTEM SHALL stop further rounds on that routine and cap credits at 1.5 maximum.

## Requirement 3: Held-Out Trial Gate for HEALED

**User Story:** As a result validator, I want HEALED verdicts to require both a dev trial and a held-out trial, so that I never allow an agent to see held-out inputs and I can be certain a port is truly fixed.

**Acceptance Criteria:**
- WHEN a routine's port returns RESURRECTED on the cold dev trial, THE SYSTEM SHALL schedule a held-out trial (seed 7, 10,000 inputs) outside the agent's view.
- IF the held-out trial also returns RESURRECTED, THEN the routine SHALL be eligible for HEALED status.
- IF the held-out trial returns UNDEAD or STILL DEAD, THEN the routine SHALL be marked UNDEAD or STILL DEAD, not HEALED.
- THE AGENT SHALL never see held-out trial inputs or results; only the run summary (HEALED or not) is relayed back.

## Requirement 4: Honest Reporting

**User Story:** As a project stakeholder, I want all outcomes—HEALED, UNDEAD, and STILL DEAD—recorded on the ledger and site with the same prominence and full metadata, so that I can audit success and failure equally.

**Acceptance Criteria:**
- WHEN a routine completes a cold test run, THE SYSTEM SHALL write the verdict (HEALED, UNDEAD, STILL DEAD, or VOID) to the ledger JSON file with routine name, pass rates per sub-domain, max ULP, median ULP, and git commit hash.
- IF the verdict is STILL DEAD or UNDEAD, THEN the ledger entry SHALL include credits spent and the stop reason (e.g., "two failed rounds").
- IF the verdict is HEALED, THEN the ledger entry SHALL include a reference to both the dev trial and held-out trial outputs.
- WHILE generating the site report, THE SYSTEM SHALL display STILL DEAD and UNDEAD outcomes with the same text prominence as HEALED, including all trial metadata and stop reasons.

## Requirement 5: Upstream Report Draft

**User Story:** As a maintainer preparing a bug report, I want a draft upstream report prepared for each HEALED flaw, so that I can review it and decide whether to file a formal issue.

**Acceptance Criteria:**
- WHEN a routine achieves HEALED status, THE SYSTEM SHALL prepare a short plaintext draft including: routine name, failing input range (tiny, small, negative, etc.), one-line description of the fix (if applicable), and trial run identifiers (seed, size, pass rates).
- THE SYSTEM SHALL not file the upstream report automatically; it SHALL be saved as a `.draft.txt` file under `.kiro/specs/<routine>/`.
- WHEN a human reviews the draft, they MAY file it manually or discard it with no further agent action.

## Requirement 6: Per-Routine Credit Cap and Stop Rule

**User Story:** As a resource manager, I want each cold test to spend at most 1.5 credits and stop after two consecutive failed rounds, so that we conserve model calls on routines that are not converging.

**Acceptance Criteria:**
- WHEN a routine begins cold test iterations, THE SYSTEM SHALL initialize a credit counter at 0 and a failed-round counter at 0.
- IF a round completes (dev trial finishes), THEN 0.75 credits SHALL be charged (two rounds = 1.5 max).
- IF a round returns UNDEAD or STILL DEAD, THEN the failed-round counter SHALL increment by 1.
- IF the failed-round counter reaches 2, THEN all further rounds on that routine SHALL be skipped, credits SHALL be capped at 1.5, and the run JSON SHALL record the stop reason "two failed rounds".
- WHEN credits on a routine reach 1.5, THEN no further rounds SHALL be attempted, regardless of verdict.

## Requirement 7: Flaw Ledger Integrity

**User Story:** As an auditor, I want the Flaw Ledger to contain only flaws measured by the pipeline, so that I can rely on every number in it.

**Acceptance Criteria:**
- THE SYSTEM SHALL update the Flaw Ledger only when a run JSON is successfully written and committed.
- EACH ledger entry SHALL reference the run JSON filename and the git commit hash of the repo at the time the run was executed.
- THE SYSTEM SHALL never add speculative or hand-typed numbers to the ledger; all data SHALL come from trial output JSON.
