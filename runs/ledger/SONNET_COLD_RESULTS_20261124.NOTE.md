# Sonnet cold runs, 24 Nov 2026 (declared in SONNET_COLD_DECLARED_20261124.md): read this before quoting them

Both were run once, as declared, and neither healed. Cold mode held in both: in the session logs the agent read only steering files, fortran/*.f and its own port. The guard logged 56 decisions and 0 blocks.

## dgamr_20261124T045708Z (claude-sonnet-4.5, 4.60 credits)
- Blind port: 34.95% (small 7.1, mid 71.6, negative 24.7). The compiled original scores 9.3 / 100 / 42.7.
- Round 1 (kept): found a real translation bug. DLGAMS used math.floor where Fortran's AINT truncates toward zero, which flipped the sign of the answer for about half the negative inputs. Sonnet found it by working one autopsy input (x = -28.56) through by hand. Negative 24.7 -> 33.0.
- Round 2 (kept, small gain): sent positive x > 10 straight to DGAMMA. Mid 71.6 -> 73.3.
- Rounds 3 and 4 (both undone): more threshold changes. Stopped after two failed rounds in a row.
- What it never found: the blind port mistyped Chebyshev coefficients (ALGMCS term 1 lost a digit, relative error 1.8e-11; 4 GAMCS terms were also off). Checked outside the repo (work/coef_check.py, work/cf2.py, same inputs as the dev trial): paste the Fortran's exact values into Sonnet's round-1 port and it scores 9.3 / 100 / 42.7, exactly the compiled original. So the whole gap to the original was one sign bug, which it fixed, plus wrong constants, which it never suspected.
- On the real flaw (x + i - 1), round 2 says "inherent rounding error, not fixable". That is the same conclusion Haiku reached.

## dlngam_20261124T050219Z (claude-sonnet-4.5, 3.13 credits)
- Blind port: 54.65% (tiny 0.3, small 60.7, near_1 6.0, near_2 41.0, mid 99.7, large 100, negative 54.2). The original scores 0.3 / 62.7 / 100 / 100 / 100 / 100 / 54.0.
- Unlike Haiku, it parsed: Sonnet joined the Fortran digit groups correctly in ALGMCS, but 3 GAMCS terms were still wrong.
- Rounds 1 and 2 (both no gain, undone): Sonnet reasoned correctly that "the compiled original passes 100% near 1, so our port differs from it", and even that "the difference must be in _dgamma". Then it chased the precision of log() near 1 (log1p) and never compared the coefficients with the DATA statements. Paste in the Fortran's values and near_1/near_2 go to 100 / 100 and the port matches the original (work/constants_counterfactual.py).

## Harness observations (not changed; changing them would be an exam change)
- The autopsy says "60-digit run also wrong, so a logic error". A mistyped constant is wrong in both runs too, so it reads as "logic" and sends the agent looking at control flow.
- The STAGE note (only "beat the original" is left) fires only when the port matches the original on every domain. No cold run got there. Even Haiku's DGAMR port missed by one negative input (42.5 vs 42.7) because of its own coefficient rounding, so no cold run was ever told the remaining job was to beat the original.
