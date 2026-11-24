# Declared before running: Sonnet cold runs for DGAMR and DLNGAM (24 Nov 2026)

Why: under cold mode (loop-frozen-2) Haiku failed both. DGAMR stayed STILL DEAD at 51% after 3 repair rounds (runs 20261124T040229Z, 20261124T040846Z). DLNGAM was DISQUALIFIED at the blind port (run 20261124T040948Z). The question now is whether a larger model does better under the same exam.

The only thing that changes is the model. Same loop, same guard, same prompts (exam at 02d4368: loop-frozen-2 plus the message-formatting fix, which changes no verdict). This is a choice made after the Haiku failures, and the write-up says so.

Each routine starts from scratch, like Haiku did. The Haiku ports are removed in the commit after this note and stay in git history (dgamr: ca3c3c2 and later; dlngam: 712b574).

Exact commands, run once each, in this order, no retries whatever the result:

    python -m harness.loop dgamr  --model claude-sonnet-4.5 --credit-cap 6.0 --cold
    python -m harness.loop dlngam --model claude-sonnet-4.5 --credit-cap 6.0 --cold

Cap 6.0 per routine: Sonnet is billed at 1.30x and Haiku at 0.40x (kiro-cli chat --list-models), and the Haiku DGAMR runs cost 1.27 in total. Default max rounds (4).

If either one heals on the dev seed, the loop's own held-out check (seed 7, n=10000) decides it. After each run I list the session's reads to confirm cold mode held, the same as for Haiku.
