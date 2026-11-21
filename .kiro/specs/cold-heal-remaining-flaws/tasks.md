# Cold Test of Remaining Flawed Originals – Tasks

## Implementation Checklist

- [x] 1. Verify DGAMMA and DCOT HEALED in committed runs. (f933cca: DGAMMA dev seed 1 n 2000 + held-out seed 7 n 10000 HEALED; 98ccc2d: DCOT 0.25 credits HEALED). _Requirements: 3, 4_

- [x] 2. harness/loop.py enforces frozen tag check: `git diff loop-frozen-1 -- harness oracle tests fortran tools .kiro/steering .kiro/agents .kiro/hooks` must be empty; if not, run marked VOID (stop reason "exam files changed during the round"). _Requirements: 2_

- [x] 3. harness/loop.py per-trial check: if exam files change during round, trial marked VOID. _Requirements: 2_

- [x] 4. harness/loop.py implements credit counter (0.75 per dev trial) and failed-round counter; increments failed counter on UNDEAD/STILL DEAD; stops at 2 failed rounds (stop reason "two_failed_rounds_in_a_row") or when spent + estimate > credit_cap (stop reason "credit_cap (...)"). _Requirements: 2, 6_

- [x] 5. harness/trial.py and harness/driver.py handle inherited flaws: driver looks in fortran/variants/ first (dgamma_fixed.f exists); inherited routines can substitute the healed port via linkage. _Requirements: 1_

- [x] 6. harness/loop.py implements stop-after-two-failures rule and records stop reason "two_failed_rounds_in_a_row". _Requirements: 2, 6_

- [x] 7. harness/transcription.py includes stop_reason, credits_spent, and round history in run JSON; run JSON shape: name, model, run_id, max_rounds, credit_cap, dev {seed,n}, heldout {seed,n,verdict,file}, start_commit, rounds[], total_credits, stop_reason, result. _Requirements: 4, 6_

- [x] 8. harness/loop.py schedules held-out trial (seed 7, n 10000) outside agent view after RESURRECTED dev trial; result recorded in run JSON. _Requirements: 3, 4_

- [x] 9. harness/verdict.py computes HEALED gate: RESURRECTED on dev AND held-out RESURRECTED AND original pass_rate < 95.0% on ≥1 sub-domain. _Requirements: 3, 4_

- [x] 10. harness/loop.py prepares upstream draft template as .kiro/specs/<routine>/<routine>.upstream.draft.txt after HEALED gate passes; not filed automatically. _Requirements: 5_

- [x] 11. harness/port_guard.py AST check (before import) blocks non-math imports and disallowed builtins; verdict DISQUALIFIED. _Requirements: 2_

- [x] 12. harness/loop.py 429 retry logic: open design question. What is the actual behavior? (See design.md Error Handling). _Requirements: 2_

- [x] 13. harness/loop.py timeout handling: open design question. What is the actual behavior? (See design.md Error Handling). _Requirements: 2_

- [x] 14. harness/transcription.py writes git commit hash and manifest sha256 to run JSON. _Requirements: 4, 7_

- [x] 15. site/tools/build.py renders STILL DEAD and UNDEAD outcomes with same prominence as HEALED, including all trial metadata, credits spent, stop reason. (Check: already builds from runs/ledger/; shows DPSI STILL DEAD, DGAMMA and DCOT HEALED). _Requirements: 4_

- [x] 16. site/tools/build.py section lists all ledger entries (HEALED, UNDEAD, STILL DEAD, VOID) sorted by routine name and trial timestamp. (Check: site displays committed runs). _Requirements: 4, 7_

- [x] 17. runs/ledger/ README documents schema and notes only committed run JSON files are included. _Requirements: 7_

- [x] 18. harness/tests/test_harness.py and test_port_trial.py include property tests for ULP metric (subnormal, ref=0, NaN, Inf). _Requirements: (correctness validation)_

- [x] 19. harness/tests/test_harness.py includes property tests for verdict derivation (RESURRECTED, HEALED, UNDEAD, STILL DEAD from pass_rate thresholds). (Check: 91 tests total, 25 in test_harness). _Requirements: (correctness validation)_

- [x] 20. harness/tests/test_loop.py includes property tests for loop termination (max 2 rounds, exit on 2 failed rounds, credit cap 1.5, held-out does not count). (Check: 17 tests in test_loop). _Requirements: (correctness validation)_

- [x] 21. harness/tests/test_guard.py confirms AST check disallows non-math imports and disallowed builtins → DISQUALIFIED. (Check: 30 tests in test_guard). _Requirements: (correctness validation)_

- [x] 22. .kiro/hooks/ guard blocks writes to harness/, oracle/, tests/, marks VOID with logging. _Requirements: 2_

- [ ] 23. Document cold test workflow in .kiro/steering/cold_test.md: entry point command, expected routines, verdict meanings, how to review upstream drafts. _Requirements: 4, 5_

- [ ] 24. Run cold test on DPSI: `python -m harness.loop dpsi --model claude-haiku-4.5`. Capture output run JSON; commit to runs/ledger/. _Requirements: 2, 4, 6_

- [ ] 25. Run cold test on DLNGAM with inherited DGAMMA port. Capture output run JSON; commit to runs/ledger/. _Requirements: 1, 2, 4_

- [ ] 26. Run cold test on DGAMR with inherited DGAMMA port. Capture output run JSON; commit to runs/ledger/. _Requirements: 1, 2, 4_

- [ ] 27. For any routine achieving HEALED, review and polish upstream draft (.kiro/specs/<routine>/<routine>.upstream.draft.txt); document reviewed status. _Requirements: 5_

- [ ] 28. After all three routines complete, check site: `python site/tools/build.py`. Verify all verdicts (STILL DEAD, UNDEAD, HEALED) visible on ledger page with equal prominence and full metadata. _Requirements: 4, 15_

- [ ] 29. Verify all numbers in Flaw Ledger come from committed run JSON files under runs/ledger/; spot-check 3 entries against source JSON. _Requirements: 4, 7_

- [ ] 30. Update README.md with cold test results: routines tested, verdicts, and for any HEALED routines, upstream report status. _Requirements: 4_
