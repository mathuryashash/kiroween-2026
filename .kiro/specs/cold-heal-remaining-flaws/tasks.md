# Cold Test of Remaining Flawed Originals – Tasks

## Implementation Checklist

- [x] 1. Verify DGAMMA and DCOT are HEALED in committed runs (dev trial + held-out trial, seed 7, 10,000 inputs). _Requirements: 3, 4_

- [ ] 2. Update harness/loop.py to accept a list of target routines (DPSI, DLNGAM, DGAMR) and enforce the frozen tag check at entry. _Requirements: 2, 4_

- [ ] 3. Add a git tag verification step to harness/loop.py: if `git rev-list -n 1 loop-frozen-1` does not match the current HEAD, output VOID and exit. _Requirements: 2_

- [ ] 4. Implement credit counter and failed-round counter in harness/loop.py: initialize at 0, charge 0.75 per round, increment failed counter on UNDEAD or STILL DEAD, exit when either limit is reached. _Requirements: 2, 6_

- [ ] 5. Extend harness/trial.py to handle inherited flaws: when linking DLNGAM or DGAMR, check if DGAMMA has a port in routines/; if so, substitute the port in the link step instead of the original Fortran. _Requirements: 1_

- [ ] 6. Add a stop-after-two-failures rule to harness/loop.py: if a routine returns UNDEAD or STILL DEAD twice in a row, skip further rounds and write stop reason to run JSON. _Requirements: 2, 6_

- [ ] 7. Extend harness.transcription to include stop_reason, credits_spent, and round history in run JSON output. _Requirements: 4, 6_

- [ ] 8. Implement held-out trial scheduling in harness/loop.py: after RESURRECTED on dev trial, launch a held-out trial (seed 7, 10,000 inputs) in a separate process or subprocess, keep the agent unaware of its inputs, and relay only the final verdict back to loop. _Requirements: 3, 4_

- [ ] 9. Add a HEALED gate in harness/loop.py: mark a routine HEALED only if both dev trial and held-out trial return RESURRECTED AND original pass_rate < 95.0 % on ≥ 1 sub-domain. _Requirements: 3, 4_

- [ ] 10. Create upstream draft template and generator in harness/loop.py: after HEALED gate passes, prepare `.kiro/specs/<routine>/<routine>.upstream.draft.txt` with routine name, failing range, one-line fix summary, and trial run identifiers; do not file automatically. _Requirements: 5_

- [ ] 11. Ensure harness/trial.py's AST check blocks any import other than `math` before import; if violation detected, return DISQUALIFIED and exit. _Requirements: 2_

- [ ] 12. Add 429 throttling retry logic to harness/loop.py: on Kiro API 429, wait 30 seconds and retry up to 3 times; if all fail, mark routine VOID with reason "API throttling". _Requirements: 2_

- [ ] 13. Add timeout handling to harness/loop.py: if any trial or agent call exceeds 15 minutes, mark routine VOID with reason "timeout" and exit. _Requirements: 2_

- [ ] 14. Extend harness.transcription to write git commit hash and manifest sha256 to every run JSON; verify in tests. _Requirements: 4, 7_

- [ ] 15. Update site/tools/build.py to render STILL DEAD and UNDEAD outcomes on the ledger and site with the same text prominence as HEALED, including all trial metadata, credits spent, and stop reason. _Requirements: 4_

- [ ] 16. Add to site/tools/build.py a section that lists all ledger entries (HEALED, UNDEAD, STILL DEAD, VOID) sorted by routine name and trial timestamp. _Requirements: 4, 7_

- [ ] 17. Update Flaw Ledger (runs/ledger/) to include a README that documents the schema and notes that only committed run JSON files are included. _Requirements: 7_

- [ ] 18. Add property tests in harness/tests/ to verify ULP metric matches verification_rules.md definition (including subnormal, ref=0, NaN, Inf cases). _Requirements: (correctness validation)_

- [ ] 19. Add property tests in harness/tests/ to verify verdict derivation (RESURRECTED, HEALED, UNDEAD, STILL DEAD) from pass_rate thresholds. _Requirements: (correctness validation)_

- [ ] 20. Add property tests in harness/tests/ to verify loop termination: max 2 rounds, exit on 2 failed rounds, credit cap 1.5. _Requirements: (correctness validation)_

- [ ] 21. Add AST safety unit test in harness/tests/ that confirms disallowed imports (non-math) and builtins (open, exec, eval, etc.) trigger DISQUALIFIED. _Requirements: (correctness validation)_

- [ ] 22. Verify guard hooks (in .kiro/hooks/) block writes to harness/, oracle/, tests/, and mark any write attempt as VOID; add logging. _Requirements: 2_

- [ ] 23. Document the cold test workflow in .kiro/steering/cold_test.md: entry point command, expected routines, verdict meanings, and how to review upstream drafts. _Requirements: 4, 5_

- [ ] 24. Run a cold test on DPSI with `python -m harness.loop dpsi --model claude-haiku-4.5`, capture the output run JSON, and commit it to runs/ledger/. _Requirements: 2, 4, 6_

- [ ] 25. Run a cold test on DLNGAM with inherited DGAMMA port, capture the output run JSON, and commit it. _Requirements: 1, 2, 4_

- [ ] 26. Run a cold test on DGAMR with inherited DGAMMA port, capture the output run JSON, and commit it. _Requirements: 1, 2, 4_

- [ ] 27. For any routine that achieves HEALED, review and polish the upstream draft (.kiro/specs/<routine>/<routine>.upstream.draft.txt) and document the reviewed status. _Requirements: 5_

- [ ] 28. After all three routines complete, regenerate the site with `python site/tools/build.py` and verify all verdicts (STILL DEAD, UNDEAD, HEALED) are visible on the ledger page with equal prominence and full metadata. _Requirements: 4, 15_

- [ ] 29. Verify all numbers in the Flaw Ledger come from committed run JSON files under runs/ledger/; spot-check 3 entries to confirm they match the JSON. _Requirements: 4, 7_

- [ ] 30. Add a final note to README.md documenting the cold test results: routines tested, verdicts, and for any HEALED routines, the upstream report status. _Requirements: 4_
