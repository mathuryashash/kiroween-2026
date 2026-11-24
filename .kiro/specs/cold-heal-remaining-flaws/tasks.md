# Cold-heal the remaining flawed originals: tasks

Done items name the commit or file that does them.

- [x] 1. Confirm the exam is unchanged since the freeze: `git diff --stat loop-frozen-1 -- harness oracle tests fortran tools .kiro/steering .kiro/agents .kiro/hooks` is empty (checked 21 Nov 2026 at 529e258). Re-run before every cold run. _Requirements: 2.1_
- [x] 2. Preflight, per-round exam check, held-out gate, undo rounds, stop rules, retries and the ledger are in harness/loop.py and covered by tests/test_loop.py. _Requirements: 2.2, 2.3, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 6.1, 6.2, 6.3, 6.4, 6.5_
- [x] 3. The agent cannot read or write the exam: resurrector.json (read and write tools only) plus tools/guard/allowlist_guard.py, covered by tests/test_guard.py; cheat probe 1 blocked 4 of 4 attempts (3fd8922). _Requirements: 2.4_
- [x] 4. DGAMMA HEALED and confirmed: dev seed 1 n 2000 and held-out seed 7 n 10000 on a clean exam (f933cca). _Requirements: 3.3_
- [x] 5. DCOT HEALED and confirmed (loop run 20261117T193644Z, 0.25 credits, 98ccc2d). Marked as not a cold test. _Requirements: 3.3, 4.3_
- [x] 6. DPSI cold run 1: STILL DEAD, stop "two_failed_rounds_in_a_row", 0.93 credits (ba04301); shown on the site. _Requirements: 4.1, 4.3, 6.3_
- [x] 7. Decided 23 Nov 2026 (by hand, not by the agent): ports stay self-contained, so the exam is unchanged and loop-frozen-1 still holds. The blind-port prompt already tells the agent to put every helper it needs in the same file, so a DLNGAM or DGAMR port carries its own literal translation of DGAMMA, inherited flaw included. Healing it is part of the cold test. _Requirements: 1.1, 2.1_
- [ ] 8. Cold run DLNGAM: `python -m harness.loop dlngam --model claude-haiku-4.5 --credit-cap 1.5`. Commit the ledger. _Requirements: 1.1, 1.2, 4.1, 6.2_
- [ ] 9. Cold run DGAMR the same way. _Requirements: 1.1, 1.2, 4.1, 6.2_
- [ ] 10. Add the ledger note for DLNGAM/DGAMR results that pass only because of the healed DGAMMA. _Requirements: 1.3_
- [x] 11. DPSI cold run 2 on the frozen loop. Planned `--credit-cap 1.5`; actually run with `--model claude-sonnet-4.5 --credit-cap 3.0` (the only change from run 1 is the model). HEALED in one round, held-out confirmed, 0.56 credits (76664c1, 845953f, 2d9f682, ledger runs/ledger/dpsi_20261122T035153Z.json). Ablation: the `x + (i - 1)` line does all the work (runs/dpsi/ablate_20261122T035821Z.json). _Requirements: 2.1, 4.1, 4.3_
- [ ] 12. For each HEALED routine, have the resurrector write .kiro/specs/cold-heal-remaining-flaws/upstream/<name>.md (routine, range, original line, fix, dev and held-out numbers with run files). A person reviews it; nothing is filed automatically. _Requirements: 5.1, 5.2_
- [ ] 13. Rebuild the site (`python site/tools/build.py`), run `python site/tools/test_site.py`, and check that every new outcome has a card with its credits and stop reason and links to its run file. _Requirements: 4.3, 4.4_
- [ ] 14. Update README.md with each cold run: routine, verdict, credits, stop reason. _Requirements: 4.3_
