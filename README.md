# GALVANI: Kiro resurrects 1980s Fortran, then stands trial

Entry for [Kiroween 2026](https://kiroween.devpost.com/) by Yashash Mathur.

## The story

Old numerical Fortran still runs underneath a lot of science. When people rewrite it—by hand or with AI—they can fix real bugs, but they can also quietly break the maths. A faithful port of a wrong original is still wrong.

GALVANI is an experiment: let an AI agent translate routines from SLATEC FNLIB, a public-domain Fortran library of special functions from the 1980s, into plain Python. Then give every port a trial against the compiled original and an independent 50-digit referee (mpmath). Never trust the agent's work without evidence.

## Results

Three routines healed (DGAMMA, DCOT, DPSI). Two stayed dead (DGAMR, DLNGAM) even after the loop tried both Haiku and Sonnet with the agent running in a cold sandbox.

**Live demo:** https://mathuryashash.github.io/kiroween-2026/ (no login needed)

**Repository:** https://github.com/mathuryashash/kiroween-2026 (public, MIT license)

## What "healed" means

The trial runs a routine on thousands of seeded random inputs, split into ranges (tiny, small, mid, large, negative, near pi, etc.). Errors are measured in ULPs, units in the last place. Each routine gets a verdict:

- **RESURRECTED**: passes in every range
- **UNDEAD**: close, but not quite
- **STILL DEAD**: fails
- **HEALED**: the original Fortran itself fails a range, and Kiro's port fixes it while keeping everything else equal

## The heals

**DGAMMA (gamma function)** — Healed.
The original fails 100% of tiny inputs. The loop `DGAMMA = DGAMMA/(X+I-1)` computes `(x + 1) - 1`, which throws away most of x's digits just before dividing by it. At x = 1e-12 the original is off by about 728 billion ULPs. Kiro's fix: `x + (i - 1)` (the integer part first). On 10,000 held-out inputs: tiny range 0% → 100%, max 1 ULP. ✓ [runs/dgamma/port_20261117T191545Z.json](runs/dgamma/port_20261117T191545Z.json)

**DCOT (cotangent)** — Healed.
Near multiples of pi, the original fails 29.5% of the time. Kiro's one-command loop fixed it in one round, 0.25 credits. Near-pi range: 72% → 100%. ✓ [runs/dcot/port_20261117T193736Z.json](runs/dcot/port_20261117T193736Z.json)

**DPSI (digamma)** — Healed (on the second try).
The original fails 86.5% for small x. Cold run 1 (Haiku, frozen loop): Kiro tried two rounds, the first made two ranges worse and the loop undid it, and the second changed nothing useful. The autopsy had pointed at line 265, `x + i - 1`, the same flaw as DGAMMA, and Kiro didn't act on it. STILL DEAD. ✗ [runs/ledger/dpsi_20261117T193921Z.json](runs/ledger/dpsi_20261117T193921Z.json)

Cold run 2: Nothing in the exam changed, nothing in Kiro's prompt changed except the commit hash. Only the model changed, from Haiku to Sonnet (the plan from day one). Sonnet read only its own file, made the same one-line fix, and held-out trial agreed. Small range 13.1% → 100%, negative range 51.6% → 100%, one round, 0.56 credits. ✓ [runs/ledger/dpsi_20261122T035153Z.json](runs/ledger/dpsi_20261122T035153Z.json) + ablation [runs/dpsi/ablate_20261122T035821Z.json](runs/dpsi/ablate_20261122T035821Z.json)

## The ones that stayed dead

**DGAMR (reciprocal gamma)** and **DLNGAM (log-gamma)** both build on DGAMMA. Under cold conditions (agent touches only its own port, sees no other ports or specs), neither healed.

**Haiku runs** (frozen loop, tag `loop-frozen-2`):
- DGAMR: 51% pass rate after 3 repair rounds, 1.27 credits total. The agent named the `x + i - 1` line every round but edited something else instead.
- DLNGAM: SyntaxError in the port (Fortran's spaces inside numbers were copied to Python as-is). Disqualified before any repair round could run. 0.55 credits.

**Sonnet runs** (same frozen loop, once each, same inputs):
- DGAMR: 38% pass rate after 4 repair rounds, 4.60 credits total. Sonnet found a real bug (AINT vs floor sign flip) but mistyped coefficients from the Fortran DATA tables account for the rest of the gap.
- DLNGAM: 54.65% pass rate after 2 repair rounds, 3.13 credits total. Same coefficient mistyping and an identical SyntaxError in the DATA constants (spaces copied to Python).

The write-up is in [runs/COLD_TEST_HAIKU_VS_SONNET.md](runs/COLD_TEST_HAIKU_VS_SONNET.md).

Both models found the right line and both left it alone. Neither attempted the fix that worked in DGAMMA and DPSI. Part of that is the exam: no cold run reached the stage where the prompt says "now beat the original"; they all stayed stuck on "matches the original." That's honest feedback about what happens when you freeze the evidence after one failure.

## How I built it (and how I used Kiro)

**Kiro CLI, headless.** Every port and repair is a headless run on `claude-haiku-4.5` by default (Sonnet 4.5 for the routines Haiku couldn't fix). Full credit ledger in [runs/credits.jsonl](runs/credits.jsonl): about 27.5 credits total.

**Custom agent.** The `resurrector` agent (.kiro/agents/resurrector.json) has no shell, only read and write tools, and permission rules that lock it into its own port files and `.kiro/specs/`.

**Guards and hooks.** On day 0 I tested whether the agent could cheat. A permission rule blocked the file write, but the same edit through PowerShell went straight through. So I added a fail-closed PreToolUse guard (.tools/guard/allowlist_guard.py) that blocks any write outside the allowlist with exit code 2. Next cheat probe: all 4 forbidden attempts blocked, no shell to try. The exam stayed clean.

**Steering docs.** Five docs in .kiro/steering/ (all `inclusion: always`): Fortran translation rules, the exact ULP metric and pass rule, what GALVANI is, the toolchain, and project rules. Kiro and the judge read the same numbers.

**Spec-driven development.** The cold-test stage is a Kiro spec (.kiro/specs/cold-heal-remaining-flaws/). Requirements, design, and task list. Kiro wrote the first draft and a revision, both committed exactly as written. I checked it against the code; the draft marked done features that don't exist. The final spec only marks a task done when it names the commit that does it.

**Property-based testing.** The trial runs thousands of seeded random inputs per range. No range is shown to the agent in advance, so it can't memorise inputs. The held-out seed was never used for tuning. This caught things unit tests would have missed.

**The loop.** `python -m harness.loop <routine>` sends Kiro the trial report, a precision autopsy (the same code run in double and in 60 digits, showing where digits are lost), and a transcription check on copied constants. Each repair is split into separate edits, and each edit is tried on its own. A round that makes any range worse is undone. History is never rewritten.

**Model choice.** Auto model ran 9.2–9.4 credits per port. Haiku ran 0.22–0.50 and found the same fixes, so the loop defaults to haiku and moves up only when it gets stuck.

**What I didn't use:** no MCP server. Fewer tools was the point.

## Why this matters

- An AI agent can find real bugs in old code. On DGAMMA and DPSI, Kiro fixed a flaw in the original. On DCOT, the loop found and healed it in one round. That's useful.
- An AI agent can't be trusted without a trial. The cold DGAMR and DLNGAM runs show the agent reading the right line and not acting on it—not because the evidence was bad (it named the line) but because the setup made the agent give up. Only changing the model and not the evidence moved it past the impasse. That's a real lesson about where to spend effort: the agent's hypothesis space, not just better steering.
- Certitude is expensive. Sonnet spent 4× as many credits as Haiku and finished worse on the scoreboard. Its reasoning was better (it found a real bug Haiku never found), but it made more errors copying numbers. For porting legacy numeric code, constants need mechanical verification, not a smarter model.
- Every claim on this site links to its source. The goal is to be honest: some routines healed, some stayed dead, and the ones that stayed dead tell you something about the limits of the setup. Judges reward working demos and good use of Kiro's features.

## Built with

- Kiro CLI 3.2.1 (headless agent)
- Python 3.13 (port code, test harness)
- mpmath (50-digit referee)
- gfortran (GCC 16, original Fortran compilation)
- pytest (test suite)
- Pyodide (in-browser Python)
- GitHub Actions (site build)
- GitHub Pages (live site)

## Testing

No login needed. Open https://mathuryashash.github.io/kiroween-2026/

1. **Flaw ledger**: the originals that fail and Kiro's pass rates on 10,000 held-out inputs.
2. **Each routine card**: original Fortran line next to Kiro's fix, spot checks computed at build time, links to run files.
3. **Re-run it yourself**: type a number, press "Run in my browser" (Pyodide loads ~10 MB once). Good test inputs: DGAMMA 1e-12, DCOT 3.14159265, DPSI 1e-7.
4. **Census**: all 36 originals tested, the 6 that fail, what happened to each.

**Local testing:**
```bash
pytest -q                    # 91 tests, all pass
python -m harness.trial dgamma --impl original --n 2000 --seed 1
python -m harness.trial dgamma --impl port --n 2000 --seed 1
python -m harness.loop dpsi --dry-run   # print the prompt without calling Kiro
```

## Open questions

- How should DLNGAM and DGAMR reach the healed DGAMMA port when both are cold? Import is blocked; call-site duplication breaks the DRY principle and leaves the original flaw in two places.
- Should the loop prompt change when moving from Haiku to Sonnet, to signal that a bigger model is in play? The runs show the prompt can matter, but only after the evidence is good.
- Could a different kind of test—not "match the original," but "beat the 50-digit referee"—have unstuck the agent earlier?

## License

MIT. See [LICENSE](LICENSE).

## Built during Kiroween 2026

Everything in this repository was written between 30 Oct 2026 (hackathon start) and 4 Dec 2026 (deadline). First commit: 12 Nov 2026 23:29 IST.
