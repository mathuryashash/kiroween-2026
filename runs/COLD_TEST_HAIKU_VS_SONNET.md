# Cold test: Haiku vs Sonnet on DGAMR and DLNGAM

24 November 2026. Every number below comes from a committed run: the loop ledgers in `runs/ledger/`, the trial JSONs in `runs/<routine>/`, and the gzipped Kiro session logs in `runs/kiro_sessions/`. Checks I ran outside the repo are marked as such, and their scripts are listed at the end.

## Why this test exists

On 24 November Kiro "healed" DLNGAM on the first try. The session log showed why: tool call 18 of 22 read `routines/dgamma.py`, the gamma port the loop had already healed on 15 November, and the gamma code inside the new port was that file with the variables renamed. It was allowed, but it was a copy, not a fix (`runs/ledger/dlngam_20261124T034238Z.NOTE.md`).

So I added a cold mode (commit 799ea7b, tag `loop-frozen-2`). While the agent runs, the guard lets it read and write only its own port. Every other port and all of `.kiro/specs/` are blocked. The loop, the prompts and the trial are otherwise the same as before. I committed each run's command and credit cap before starting it, and each one ran once, with no retries.

DGAMR (reciprocal gamma) and DLNGAM (log-gamma) both lean on DGAMMA. DGAMMA's real flaw is one line, `DGAMMA = DGAMMA/(X+I-1)`. For a tiny `x`, `x + i - 1` loses `x` to rounding, so any literal port fails on small inputs exactly where the compiled Fortran fails. Healing a cold port means translating everything faithfully first, then fixing that line.

## Results

| Run | Model | Credits | Rounds | Final dev trial | Compiled original, same inputs |
|---|---|---|---|---|---|
| DGAMR 040229Z + 040846Z | Haiku 4.5 | 1.27 | 3 repair | STILL DEAD 51.0% (small 9.3, mid 100, negative 42.5) | 9.3 / 100 / 42.7 |
| DLNGAM 040948Z | Haiku 4.5 | 0.55 | 0 | DISQUALIFIED (port does not parse) | – |
| DGAMR 045708Z | Sonnet 4.5 | 4.60 | 4 repair | STILL DEAD 38.05% best (small 7.1, mid 73.3, negative 33.0) | 9.3 / 100 / 42.7 |
| DLNGAM 050219Z | Sonnet 4.5 | 3.13 | 2 repair | STILL DEAD 54.65% (near_1 6.0, near_2 41.0) | near_1 100, near_2 100, all others equal |

Total: Haiku 1.82 credits, Sonnet 7.73. Cold mode held in all four: the guard blocked nothing, and no session opened another port or a spec.

Neither model healed either routine. They failed in different ways, though, and the differences are the useful part.

## Where they differed

### 1. Copying the Fortran: Haiku got the numbers right, Sonnet got the syntax right

The routines carry long tables of Chebyshev coefficients written like `+.1666389480 4518632472 0572965082 2 D+0`. Fortran ignores the spaces inside numbers; Python doesn't allow them.

- Haiku's DLNGAM port copied those spaces as they were. Every value was correct, but the file doesn't parse, so the port was disqualified before any repair round. Its DGAMR port wrote the values out to about 19 digits. That was close enough: the mid range matched the original at 100%.
- Sonnet wrote valid Python every time, but changed digits along the way. In DGAMR, the first ALGMCS term came out as `0.16663894804818…` instead of `0.16663894804518…` (relative error 1.8e-11), and four GAMCS terms were off. In DLNGAM, three GAMCS terms were off.

Those few wrong constants account for all of Sonnet's extra failures. Outside the repo I pasted the Fortran's exact values into Sonnet's ports and trialled them on the same inputs. Its DGAMR port (after its own round-1 fix) then scores 9.3 / 100 / 42.7, and its DLNGAM port scores 100 / 100 near 1 and 2. Both match the compiled original exactly.

### 2. Diagnosis: Haiku went to the right line and stopped there; Sonnet traced inputs by hand

- Haiku read the autopsy, went straight to `dgamma_val / (x + i - 1)`, and correctly said it loses precision for small `x`. Then it noted that the compiled original fails on the same inputs and concluded the flaw is "fundamental" in double precision. In all three rounds it named the line and edited something else.
- Sonnet worked one failing input through on paper. For `x = -28.56` it saw that the sign was wrong, then traced it to a real translation bug in its own DLGAMS: it had used `math.floor` where Fortran's `AINT` truncates toward zero, which flips the sign for about half of all negative inputs. That fix was kept (negative 24.7% → 33.0%). It was the only real bug either model found in a repair round.
- Sonnet also compared itself with the original in a way Haiku didn't. In DLNGAM it wrote: "the compiled Fortran passes 100% on near_1 … so the difference must be in `_dgamma`." That was the right inference, one step from the answer. Then it went off to the precision of `log()` near 1 (it tried `log1p` twice) instead of checking `_dgamma`'s constants against the DATA statements.

### 3. Repair strategy: Haiku repeated one idea; Sonnet tried a new one each round

- Haiku made the same move in every DGAMR round: send small `|x|` down the log-gamma path. That path ends in the same flawed DGAMMA, so nothing improved, and the loop undid every round.
- Sonnet had a different hypothesis each round: the sign bug, then the `x > 10` threshold, then `log1p`. It read the loop's per-change test results and acted on them, for example "the trunc fix from Round 1 is kept since ablation showed it helps negative". Of its 6 rounds, 2 were kept. Haiku kept 0 of 3.

### 4. Where both ended up: "inherent, not fixable"

The models disagree on almost everything else, but they agree about the real flaw. Sonnet's DGAMR round 2 calls `x + i - 1` "inherent rounding error, not fixable", which is the same conclusion as Haiku. Neither tried the one-line fix, writing it as `x + (i - 1)` so the integer part is added first.

Part of that is the setup, not the models:

- **The autopsy's wording misled them.** When a 60-digit rerun of the same code is also wrong, the autopsy calls it "a logic error". A mistyped constant is wrong at 60 digits too, so it gets labelled "logic", which sent Sonnet looking at control flow. Sonnet quoted that line back in DGAMR rounds 2 and 3 and DLNGAM rounds 1 and 2.
- **No cold run reached the "beat the original" stage.** The loop only tells the agent "translation is done; now beat the original" once the port matches the original on every sub-domain. No cold port got there. Haiku's DGAMR came closest, one negative input short (42.5% vs 42.7%), because of its own rounding of the coefficients. So no cold run was ever told that the remaining job was to beat the original, and both models kept treating the flaw as something to copy faithfully.

I haven't changed either behaviour. Both are part of the frozen exam, and changing them after seeing these results would be tuning the exam to the answer.

### 5. Cost

Sonnet is billed at 1.30× and Haiku at 0.40× (`kiro-cli chat --list-models`). Sonnet also read more and wrote longer replies. A Sonnet blind port cost 1.55–1.83 credits; Haiku's cost 0.55–0.62. Sonnet repair rounds cost 0.46–1.02, Haiku's 0.16–0.31. Overall Sonnet spent about 4× as much on these two routines and finished worse on the scoreboard. Its reasoning was better, but its copy of the coefficients was worse.

## What this shows about Kiro

- **The guard caught what verdicts alone would miss.** The DLNGAM "heal" passed the held-out check at 100%. Only reading which files the session touched showed it was a copy.
- **A bigger model doesn't make a more faithful copy.** Sonnet reasoned better and found a real bug Haiku never had to find, but it introduced errors in the boring part, copying numbers, that a smaller model got right. For porting legacy numeric code, the constants need a mechanical check, not a smarter model.
- **Both models fixed DGAMMA when the setup let them, and neither did cold.** The DGAMMA heal on 15 November happened with the fixed line visible to later runs. Under cold conditions, both models found the line and both left it alone.

## Evidence

- Plan committed before each run: `runs/ledger/SONNET_COLD_DECLARED_20261124.md` (commit cb8947e). The Haiku runs were declared in their own notes before running.
- Notes: `runs/ledger/dlngam_20261124T034238Z.NOTE.md`, `dgamr_20261124T040229Z.NOTE.md`, `dgamr_20261124T040846Z.NOTE.md`, `dlngam_20261124T040948Z.NOTE.md`, `SONNET_COLD_RESULTS_20261124.NOTE.md`.
- Cold mode: `tools/guard/allowlist_guard.py`, `harness/loop.py --cold`, tests `tests/test_guard_cold.py` and `tests/test_loop_cold.py`.
- Credits: `runs/credits.jsonl`.
- Checks run outside the repo, so the exam stays untouched: `coef_check.py` (each coefficient against the Fortran DATA statements), `constants_counterfactual.py` and `cf2.py` (the ports with the Fortran's exact constants pasted in, trialled with `harness.ablate.trial_ablation`, seed 1, n=2000), and `helper_check.py` (each helper function against mpmath). Copies are in `D:/hackathons/kiroween/work/compare/evidence/`.
