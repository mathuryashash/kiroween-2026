"""
harness/loop.py - GALVANI's self-healing loop, one command, no human in it.

  python -m harness.loop <name> [--model claude-haiku-4.5] [--max-rounds 4] [--credit-cap 3.0]
                                [--agent-cmd "<template with {model}>"] [--dry-run] [--start port|repair]

Flow: (blind port if routines/<name>.py does not exist) -> dev trial -> evidence (trial report,
precision autopsy of the worst failing inputs, per-hunk ablation of the previous round, the agent's
own earlier diffs) -> Kiro resurrector repairs -> commit VERBATIM -> dev trial again. A round that
makes any sub-domain worse is undone by a NEW commit (history is never rewritten) and its ablation is
shown to the agent next round. On a dev-trial success the held-out trial (other seed, 5x inputs,
never shown to the agent) must agree before the result counts.

What the loop guarantees:
  - routines/*.py is only ever written by the agent; the loop commits it exactly as written.
  - every prompt the agent received is committed next to the change it produced.
  - the exam must be clean in git before the loop starts and before every trial (else VOID, stop).
  - the agent never sees held-out inputs, the referee or the compiled original's source of truth.
What it does not guarantee: that the agent finds the fix, or that a fix generalises beyond the
held-out trial. The held-out trial and the overfit guard make cheating visible, not impossible.
"""

import argparse
import gzip
import json
import math
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

EXAM_PATHS = ["harness", "oracle", "tests", "fortran", "tools",
              ".kiro/steering", ".kiro/agents", ".kiro/hooks"]
AGENT_WRITABLE = ("routines/", ".kiro/specs/")

DEV = (1, 2000)          # (seed, n) shown to the agent through the feedback
HELDOUT = (7, 10000)     # never shown to the agent
ABLATE_N = 300
FAIL_DROP = 1.0          # a sub-domain losing more than this many points = regression
DEFAULT_ROUND_CREDITS = 0.5
AGENT_TIMEOUT_S = 900
RETRY_WAITS_S = (30, 90)  # backoff before attempts 2 and 3 (429 / timeouts)

DEFAULT_AGENT_CMD = ("kiro-cli chat --v3 --no-interactive --trust-all-tools --agent resurrector "
                     "--model {model} --output-format stream-json")

KNOWN_CONSTANTS = [math.pi, math.pi / 2, math.pi / 4, 2 / math.pi, 1 / math.pi, math.e,
                   math.log(2), math.log(10), math.sqrt(2), math.sqrt(math.pi),
                   1 / math.sqrt(math.pi), 2 / math.sqrt(math.pi), 0.5772156649015329,
                   math.log(2 * math.pi) / 2, math.sqrt(2 * math.pi)]


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# ----------------------------------------------------------------------------- git

def _git(*args, check=True) -> str:
    r = subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True,
                       timeout=60)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()[:400]}")
    return r.stdout


def _status(paths=()) -> list[str]:
    out = _git("status", "--porcelain", "--untracked-files=all", "--", *paths)
    return [ln[3:].strip().strip('"') for ln in out.splitlines() if ln.strip()]


def exam_dirty() -> list[str]:
    return _status(EXAM_PATHS)


def _commit(message: str, files: list) -> str:
    rel = [str(Path(f).resolve().relative_to(REPO_ROOT)).replace("\\", "/") if Path(f).is_absolute()
           else str(f) for f in files]
    _git("add", "--", *rel)
    _git("commit", "-q", "-m", message)
    return _git("rev-parse", "HEAD").strip()


def _restore_port(name: str, rev: str, message: str) -> str:
    """Undo a round with a NEW commit that puts routines/<name>.py back as it was at rev."""
    _git("checkout", rev, "--", f"routines/{name}.py")
    return _commit(message, [f"routines/{name}.py"])


# ----------------------------------------------------------------------------- trials & evidence

def trial_port(name: str, seed: int, n: int, label: str, dry: bool = False) -> tuple[dict, Path | None]:
    """Run a port trial, write its JSON and commit it at once (the run file is evidence).
    A dry run trials but writes and commits nothing."""
    from harness.trial import run_trial, write_run
    result = run_trial(name, "port", n, seed)
    if dry:
        return result, None
    path = write_run(name, "port", result)
    files = [path] + [p for p in [path.parent / "latest.json"] if p.exists()]
    _commit(f"{name} {label} trial (seed {seed}, n={n}): {result['verdict']} "
            f"{result['overall_pass_rate']:.2f}%", files)
    return result, path


def build_feedback(trial: dict) -> str:
    from harness.feedback import build_feedback as _bf
    return _bf(trial)


def build_autopsy(name: str, xs: list) -> str:
    from harness.autopsy import autopsy, format_report
    from oracle.referees import get_referee
    mpfn = get_referee(name)["mpfn"]
    parts = []
    for x in xs:
        try:
            parts.append(format_report(autopsy(name, x, reference=mpfn)))
        except Exception as exc:                       # the autopsy itself must never stop the loop
            parts.append(f"autopsy of x={x!r} failed: {type(exc).__name__}: {exc}")
    return "\n".join(parts)


def build_transcription(name: str) -> str:
    from harness.transcription import check, format_report
    try:
        return format_report(name, check(name))
    except Exception as exc:
        return f"transcription check failed: {type(exc).__name__}: {exc}\n"


def build_ablation(name: str, before_rev: str, after_rev: str) -> str:
    from harness.ablate import ablate, format_report
    try:
        return format_report(ablate(name, before_rev, after_rev, n=ABLATE_N, seed=DEV[0]))
    except Exception as exc:
        return f"ablation failed: {type(exc).__name__}: {exc}\n"


def _min_pass(trial: dict) -> float:
    return min(s["pass_rate"] for s in trial["domain_stats"].values())


def _failing_inputs(trial: dict, k: int = 3) -> list:
    fails = sorted((s["pass_rate"], s.get("worst_x")) for s in trial["domain_stats"].values()
                   if s["pass_rate"] < 99.0 and s.get("worst_x") is not None)
    return [x for _, x in fails[:k]]


def _regressions(before: dict, after: dict) -> list[str]:
    out = []
    for d, s in after["domain_stats"].items():
        b = before["domain_stats"].get(d)
        if b is not None and s["pass_rate"] < b["pass_rate"] - FAIL_DROP:
            out.append(f"{d} {b['pass_rate']:.2f}% -> {s['pass_rate']:.2f}%")
    return out


def _gains(before: dict, after: dict) -> list[str]:
    out = []
    for d, s in after["domain_stats"].items():
        b = before["domain_stats"].get(d)
        if b is not None and s["pass_rate"] > b["pass_rate"] + FAIL_DROP:
            out.append(f"{d} {b['pass_rate']:.2f}% -> {s['pass_rate']:.2f}%")
    return out


def _matches_original(trial: dict) -> bool:
    orig = trial.get("original_on_same_inputs") or {}
    return bool(orig) and all(d in orig and abs(s["pass_rate"] - orig[d]["pass_rate"]) <= 0.01
                              for d, s in trial["domain_stats"].items())


def _is_success(trial: dict) -> bool:
    if trial["verdict"] == "RESURRECTED":
        return True
    if trial["verdict"] != "HEALED":
        return False
    orig = trial.get("original_on_same_inputs") or {}
    return all(s["pass_rate"] >= orig.get(d, {}).get("pass_rate", 0.0) - FAIL_DROP
               for d, s in trial["domain_stats"].items())


# ----------------------------------------------------------------------------- overfit guard

_LIT = re.compile(r"(?<![\w.])(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?(?![\w.])")


def _sig_digits(mant: str) -> int:
    return len(mant.replace(".", "").lstrip("0").rstrip("0") if "." in mant else mant.lstrip("0")) or 1


def check_overfit(diff_text: str, shown_inputs: list, before_text: str = "") -> list[str]:
    """Flag literals added by the diff that copy an input the agent was shown.

    Ignored: literals already in the code before the round, well-known constants, integers and
    literals with fewer than 4 significant digits (too short to be a copied input). A literal is
    flagged when it equals a shown input to its own written precision."""
    existing = set()
    for m in _LIT.finditer(before_text):
        try:
            existing.add(float(m.group(0)))
        except ValueError:
            pass
    findings = []
    for line in diff_text.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        code = line[1:].split("#", 1)[0]               # comments may name the failing inputs
        for m in _LIT.finditer(code):
            mant, exp = m.group(1), m.group(2) or ""
            try:
                v = float(mant + exp)
            except ValueError:
                continue
            sig = _sig_digits(mant)
            if v in existing or sig < 4 or (v == int(v) and abs(v) < 1e6):
                continue
            if any(abs(v - c) <= 1e-14 * abs(c) for c in KNOWN_CONSTANTS):
                continue
            tol = 0.5 * 10.0 ** (1 - sig)
            for x in shown_inputs:
                if x and abs(v - abs(x)) <= tol * abs(x):
                    findings.append(f"added literal {mant + exp} equals shown input {x!r}: "
                                    f"{code.strip()[:120]}")
                    break
    return findings


# ----------------------------------------------------------------------------- the agent

def parse_credits_and_text(log_path: Path) -> tuple[float, str]:
    from harness.kiro_session import parse_session
    info = parse_session(log_path)
    return info["credits"], info["final_text"]


def _agent_argv(template, model: str) -> list[str]:
    if isinstance(template, (list, tuple)):
        parts = [str(p).format(model=model) for p in template]
    else:
        parts = [p.strip('"') for p in shlex.split(template.format(model=model), posix=False)]
    return [shutil.which(parts[0]) or parts[0], *parts[1:]]


def call_agent(prompt: str, model: str, tag: str, cmd_template=None, changed=None) -> dict:
    """Run the Kiro resurrector (with retries). The prompt is passed as one argv element.

    Retries on throttling (429), timeouts and non-zero exits, but never after the agent has
    already changed the port (`changed()` is true): a retry would start from a half-edited file,
    so the loop takes that change as the round's result instead."""
    cmd = [*_agent_argv(cmd_template or DEFAULT_AGENT_CMD, model), prompt]
    sess_dir = REPO_ROOT / "runs" / "kiro_sessions"
    sess_dir.mkdir(parents=True, exist_ok=True)
    tries = []
    for attempt in range(1, len(RETRY_WAITS_S) + 2):
        base = sess_dir / f"{tag}_try{attempt}"
        log, err = base.with_suffix(".jsonl"), base.with_suffix(".err")
        timed_out = False
        with open(log, "wb") as fo, open(err, "wb") as fe:
            try:
                rc = subprocess.run(cmd, stdout=fo, stderr=fe, cwd=str(REPO_ROOT),
                                    timeout=AGENT_TIMEOUT_S).returncode
            except subprocess.TimeoutExpired:
                rc, timed_out = -1, True
        gz = log.with_suffix(".jsonl.gz")
        with open(log, "rb") as fi, gzip.open(gz, "wb") as fo:
            shutil.copyfileobj(fi, fo)
        log.unlink()
        credits, text = parse_credits_and_text(gz)
        err_text = err.read_text(encoding="utf-8", errors="replace")
        err.unlink()
        throttled = "429" in err_text or "THROTTL" in err_text.upper() or "RATE_EXCEEDED" in err_text
        tries.append({"attempt": attempt, "rc": rc, "timed_out": timed_out, "throttled": throttled,
                      "credits": credits, "log": str(gz.relative_to(REPO_ROOT)).replace("\\", "/"),
                      "stderr_tail": "" if rc == 0 else err_text[-400:]})
        if rc == 0 and text.strip():
            return {"ok": True, "credits": sum(t["credits"] for t in tries), "final_text": text,
                    "logs": [t["log"] for t in tries], "tries": tries}
        if changed is not None and changed():
            break
        if attempt <= len(RETRY_WAITS_S):
            wait = RETRY_WAITS_S[attempt - 1]
            print(f"  [loop] agent attempt {attempt} failed (rc={rc}, timeout={timed_out}, "
                  f"throttled={throttled}); retry in {wait}s", flush=True)
            time.sleep(wait)
            continue
        break
    return {"ok": False, "credits": sum(t["credits"] for t in tries), "final_text": text,
            "logs": [t["log"] for t in tries], "tries": tries,
            "error": f"agent failed after {len(tries)} attempt(s); last rc={tries[-1]['rc']}"}


# ----------------------------------------------------------------------------- prompts

def blind_port_prompt(name: str) -> str:
    return (
        f"Port the SLATEC FNLIB routine {name.upper()} to Python as routines/{name}.py.\n\n"
        f"Read the steering files in .kiro/steering/ first, then fortran/slatec/{name}.f and every "
        f"routine it calls (in fortran/slatec/ or fortran/support/). Translate literally, as the "
        f"steering rules say: same evaluation order, same constants, same branches. Do not improve "
        f"the algorithm. routines/{name}.py must define {name}(x: float) -> float and import nothing "
        f"but math; put the helpers it needs (series evaluation, initialisation, machine constants) "
        f"in the same file. You cannot run code: a trial harness outside your session will judge "
        f"the port. When done, say in at most 8 lines what you translated.")


def _cap(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + f"\n... ({len(text) - limit} characters cut)\n"


STAGE_HEAL = (
    "STAGE: the translation is done. Your port now fails exactly where the compiled original fails, "
    "so the remaining failures are flaws of the original algorithm, and a faithful copy of a failing "
    "original stays STILL DEAD. Your job in this round is to make the port do better than the "
    "original on the failing inputs while keeping every passing sub-domain as it is. A port that "
    "beats the original on its failing sub-domain and keeps the rest earns HEALED.")


def repair_prompt(name: str, k: int, max_rounds: int, history: str, feedback: str,
                  autopsy: str, ablation: str, transcription: str = "", stage: str = "") -> str:
    # The prompt travels as one command-line argument (Windows limit 32,767 characters).
    history, autopsy, ablation = _cap(history, 6000), _cap(autopsy, 9000), _cap(ablation, 5000)
    p = [f"GALVANI evidence for routines/{name}.py, repair round {k} of at most {max_rounds}."]
    if transcription:
        p += ["", "TRANSCRIPTION CHECK (constants in your port compared with the DATA statements of "
              "the Fortran original; a copying error makes every later diagnosis unreliable, so "
              "fix these first):", _cap(transcription, 3000).rstrip()]
    if history:
        p += ["", "WHAT HAPPENED IN EARLIER ROUNDS (your own changes and their trial results):", history]
    p += ["", "TRIAL REPORT (the harness ran the port on its dev inputs):", feedback.rstrip()]
    if autopsy:
        p += ["", "PRECISION AUTOPSY of the worst failing inputs. The same code runs twice, in IEEE "
              "double and in 60-digit arithmetic. The report names the first line where a value "
              "drifts away from its 60-digit shadow (a rounding cause), or, when the 60-digit run is "
              "wrong too, lists what each assignment computed (a logic cause):", autopsy.rstrip()]
    if ablation:
        p += ["", "ABLATION of your previous change (each hunk undone on its own, then trialled):",
              ablation.rstrip()]
    if stage:
        p += ["", stage]
    p += ["", f"Task: using this evidence, repair routines/{name}.py with str_replace edits only. "
          "Keep what the report shows is working; undo or correct what the evidence shows is broken. "
          "Prefer the smallest edit and remove code that is not needed. Do not special-case the "
          "inputs shown above: a held-out trial on inputs you have not seen decides the verdict. "
          "Above any changed line, add a comment naming the failing inputs and the cause. Do not "
          "touch any other file. You cannot run code. When done, state the exact change and your "
          "explanation in at most 8 lines."]
    return "\n".join(p) + "\n"


def _round_history(name: str, rounds: list) -> str:
    out = []
    for r in rounds:
        if r.get("type") not in ("repair", "reverted", "rejected", "no_diff", "no_gain"):
            continue
        line = f"Round {r['round']}: "
        if r["type"] == "no_diff":
            out.append(line + "you made no change to the file.")
            continue
        line += {"repair": "kept.", "reverted": "UNDONE because it made the port worse: "
                 + "; ".join(r.get("regressions", [])),
                 "rejected": "UNDONE by the overfit guard: " + "; ".join(r.get("overfit", [])),
                 "no_gain": "UNDONE because no sub-domain improved"}[r["type"]]
        if r.get("trial_after"):
            line += f" Trial after it: {r['trial_after']}."
        diff = _git("diff", f"{r['commit']}^", r["commit"], "--", f"routines/{name}.py", check=False)
        dl = [ln for ln in diff.splitlines() if ln[:1] in "+-@" and not ln.startswith(("+++", "---"))]
        out += [line, "Your diff in that round:", *dl[:60]]
        if len(dl) > 60:
            out.append(f"... ({len(dl) - 60} more diff lines)")
    return "\n".join(out)


def _trial_line(t: dict) -> str:
    return (f"{t['verdict']}, overall {t['overall_pass_rate']:.2f}%, "
            + ", ".join(f"{d} {s['pass_rate']:.1f}%" for d, s in t["domain_stats"].items()))


# ----------------------------------------------------------------------------- the loop

def loop(name: str, model: str = "claude-haiku-4.5", max_rounds: int = 4, credit_cap: float = 3.0,
         agent_cmd: str | None = None, dry_run: bool = False, start: str = "port") -> dict:
    port = REPO_ROOT / "routines" / f"{name}.py"
    run_id = _stamp()
    ev_dir = REPO_ROOT / "runs" / name / "loop" / run_id
    ledger = {"name": name, "model": model, "run_id": run_id, "max_rounds": max_rounds,
              "credit_cap": credit_cap, "dev": {"seed": DEV[0], "n": DEV[1]},
              "heldout": {"seed": HELDOUT[0], "n": HELDOUT[1]}, "start_commit": None,
              "rounds": [], "total_credits": 0.0, "stop_reason": None, "result": None}

    dirty = exam_dirty()
    if dirty:
        print("[loop] PREFLIGHT FAILED: exam files are not clean in git; every trial would be VOID.")
        for f in dirty[:20]:
            print("   ", f)
        return {**ledger, "error": "exam_dirty", "dirty_files": dirty}
    if _status([f"routines/{name}.py"]):
        print(f"[loop] PREFLIGHT FAILED: routines/{name}.py has uncommitted changes.")
        return {**ledger, "error": "port_dirty"}
    if start == "repair" and not port.exists():
        print(f"[loop] PREFLIGHT FAILED: --start repair but routines/{name}.py does not exist.")
        return {**ledger, "error": "no_port"}
    ledger["start_commit"] = _git("rev-parse", "HEAD").strip()
    ev_dir.mkdir(parents=True, exist_ok=True)

    def stop(reason: str):
        ledger["stop_reason"] = reason
        print(f"[loop] stop: {reason}", flush=True)

    # ---- step 0: blind port
    if not port.exists():
        prompt = blind_port_prompt(name)
        if dry_run:
            print("[loop] DRY RUN, blind port prompt:\n" + prompt)
            stop("dry_run")
            return ledger
        (ev_dir / "r0_prompt.txt").write_text(prompt, encoding="utf-8", newline="\n")
        res = call_agent(prompt, model, f"{name}_{run_id}_r0", agent_cmd, changed=port.exists)
        ledger["total_credits"] += res["credits"]
        if not port.exists():
            c = _commit(f"{name} blind port by Kiro resurrector on {model} FAILED "
                        f"({res['credits']:.2f} credits): {res.get('error', 'no file written')}",
                        [ev_dir / "r0_prompt.txt", *res["logs"]])
            ledger["rounds"].append({"round": 0, "type": "port_failed", "commit": c,
                                     "credits": res["credits"]})
            stop("port_failed")
            return _finish(name, ledger, ev_dir)
        note = "" if res["ok"] else f" [session ended badly: {res.get('error')}]"
        c = _commit(f"{name} blind port by Kiro resurrector on {model} (verbatim, "
                    f"{res['credits']:.2f} credits){note}: {_first_line(res['final_text'])}",
                    [port, ev_dir / "r0_prompt.txt", *res["logs"], *_spec_files()])
        ledger["rounds"].append({"round": 0, "type": "port", "commit": c, "credits": res["credits"]})

    trial, trial_path = trial_port(name, *DEV, label="dev", dry=dry_run)
    print(f"[loop] dev trial: {_trial_line(trial)}", flush=True)
    last_change = None          # (before_rev, after_rev) of the previous agent change
    fails_in_row = no_diff = 0

    if dry_run and _is_success(trial):
        print("[loop] DRY RUN: the port already passes the dev trial; nothing to repair.")
        stop("dry_run")
        return ledger

    for k in range(1, max_rounds + 1):
        if trial["verdict"] in ("VOID", "DISQUALIFIED"):
            stop(f"trial_{trial['verdict'].lower()}")
            break
        if _is_success(trial):
            break
        spent = [r["credits"] for r in ledger["rounds"] if r.get("credits")]
        estimate = max(spent) if spent else DEFAULT_ROUND_CREDITS
        if ledger["total_credits"] + estimate > credit_cap:
            stop(f"credit_cap ({ledger['total_credits']:.2f} spent + ~{estimate:.2f} > {credit_cap})")
            break

        xs = _failing_inputs(trial)
        feedback = build_feedback(trial)
        autopsy = build_autopsy(name, xs) if xs else ""
        ablation = build_ablation(name, *last_change) if last_change else ""
        transcription = build_transcription(name)
        stage = STAGE_HEAL if _matches_original(trial) and not transcription else ""
        prompt = repair_prompt(name, k, max_rounds, _round_history(name, ledger["rounds"]),
                               feedback, autopsy, ablation, transcription, stage)
        if dry_run:
            print(f"[loop] DRY RUN, round {k} prompt:\n" + prompt)
            stop("dry_run")
            return ledger
        pfile = ev_dir / f"r{k}_prompt.txt"
        pfile.write_text(prompt, encoding="utf-8", newline="\n")

        print(f"[loop] round {k}: calling the agent ({model})", flush=True)
        before_rev = _git("rev-parse", "HEAD").strip()
        status_before = set(_status(EXAM_PATHS))
        port_changed = lambda: bool(_git("diff", "--", f"routines/{name}.py").strip())
        res = call_agent(prompt, model, f"{name}_{run_id}_r{k}", agent_cmd, changed=port_changed)
        ledger["total_credits"] += res["credits"]
        evidence = [pfile, *res["logs"]]

        # Exam files are what a verdict depends on. Writes elsewhere are already denied by the
        # agent's permission rules; watching only the exam keeps human edits to the site or docs
        # during a long run from stopping it (loop run 20261117T193234Z stopped on such an edit).
        touched = sorted(set(_status(EXAM_PATHS)) - status_before)
        if touched:                                      # the guard should make this impossible
            stop("exam files changed during the round: " + ", ".join(touched[:5]))
            ledger["rounds"].append({"round": k, "type": "guard_breach", "files": touched})
            break
        diff = _git("diff", "--", f"routines/{name}.py")
        if not diff.strip() and not res["ok"]:
            c = _commit(f"{name} round {k}: agent failed ({res['credits']:.2f} credits): "
                        f"{res['error']}", evidence)
            ledger["rounds"].append({"round": k, "type": "agent_error", "commit": c,
                                     "credits": res["credits"], "error": res["error"]})
            stop("agent_error")
            break
        if not diff.strip():
            no_diff += 1
            c = _commit(f"{name} round {k}: Kiro resurrector on {model} made no change "
                        f"({res['credits']:.2f} credits)", evidence)
            ledger["rounds"].append({"round": k, "type": "no_diff", "commit": c, "credits": res["credits"]})
            if no_diff >= 2:
                stop("no_diff_twice")
                break
            continue
        no_diff = 0

        before_text = _git("show", f"HEAD:routines/{name}.py", check=False)
        overfit = check_overfit(diff, xs, before_text)
        note = "" if res["ok"] else f" [session ended badly: {res.get('error')}]"
        c = _commit(f"{name} round {k} by Kiro resurrector on {model} (verbatim, "
                    f"{res['credits']:.2f} credits){note}: {_first_line(res['final_text'])}",
                    [port, *evidence, *_spec_files()])
        entry = {"round": k, "commit": c, "credits": res["credits"],
                 "agent_text": res["final_text"][-600:], "trial_before": _trial_line(trial)}

        if overfit:
            r = _restore_port(name, before_rev, f"{name} round {k} undone by the overfit guard: "
                              + overfit[0][:150])
            ledger["rounds"].append({**entry, "type": "rejected", "overfit": overfit, "undo_commit": r})
            last_change = (before_rev, c)
            fails_in_row += 1
        else:
            new, new_path = trial_port(name, *DEV, label=f"round {k} dev")
            print(f"[loop] round {k} dev trial: {_trial_line(new)}", flush=True)
            regs = _regressions(trial, new) if new["verdict"] not in ("VOID",) else ["trial VOID"]
            gains = _gains(trial, new)
            entry["trial_after"] = _trial_line(new)
            entry["trial_after_file"] = str(new_path.relative_to(REPO_ROOT)).replace("\\", "/")
            if not regs and not gains and not _is_success(new):
                # Keep only changes that measurably help: a change with no gain moves the port
                # away from the literal translation without evidence that it is needed.
                r = _restore_port(name, before_rev, f"{name} round {k} undone: no sub-domain improved")
                ledger["rounds"].append({**entry, "type": "no_gain", "undo_commit": r})
                last_change = (before_rev, c)
                fails_in_row += 1
            elif regs:
                r = _restore_port(name, before_rev, f"{name} round {k} undone: it made the port "
                                  f"worse ({'; '.join(regs)[:150]})")
                ledger["rounds"].append({**entry, "type": "reverted", "regressions": regs, "undo_commit": r})
                last_change = (before_rev, c)
                fails_in_row += 1
            else:
                ledger["rounds"].append({**entry, "type": "repair"})
                last_change = (before_rev, c)
                trial, trial_path = new, new_path
                fails_in_row = 0
        if fails_in_row >= 2:
            stop("two_failed_rounds_in_a_row")
            break

    if ledger["stop_reason"] is None:
        if _is_success(trial):
            held, held_path = trial_port(name, *HELDOUT, label="held-out")
            print(f"[loop] held-out trial: {_trial_line(held)}", flush=True)
            ledger["heldout"].update(verdict=held["verdict"], file=str(held_path.relative_to(REPO_ROOT)).replace("\\", "/"))
            if _is_success(held):
                ledger["result"] = held["verdict"]
                stop(f"{held['verdict'].lower()}_confirmed")
            else:
                stop("heldout_disagrees")
        else:
            stop("max_rounds")
    ledger["final_dev_trial"] = _trial_line(trial)
    return _finish(name, ledger, ev_dir)


def _first_line(text: str) -> str:
    """The agent's closing summary (the end of its reply), squeezed to one line for a commit."""
    t = " ".join(text.split())
    return (t[-100:] if len(t) > 100 else t) or "(no message)"


def _spec_files() -> list[str]:
    return [f for f in _status([".kiro/specs"])]


def _finish(name: str, ledger: dict, ev_dir: Path) -> dict:
    ledger["end"] = _stamp()
    ledger["total_credits"] = round(ledger["total_credits"], 4)
    out = REPO_ROOT / "runs" / "ledger" / f"{name}_{ledger['run_id']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ledger, indent=2), encoding="utf-8", newline="\n")
    _commit(f"{name} loop {ledger['run_id']}: {ledger['stop_reason']} "
            f"({ledger['total_credits']:.2f} credits)", [out])
    print(f"[loop] ledger: {out.relative_to(REPO_ROOT)}  credits: {ledger['total_credits']:.2f}")
    return ledger


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GALVANI self-healing loop")
    ap.add_argument("name")
    ap.add_argument("--model", default="claude-haiku-4.5")
    ap.add_argument("--max-rounds", type=int, default=4)
    ap.add_argument("--credit-cap", type=float, default=3.0)
    ap.add_argument("--agent-cmd")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--start", choices=["port", "repair"], default="port")
    a = ap.parse_args(argv)
    led = loop(a.name, a.model, a.max_rounds, a.credit_cap, a.agent_cmd, a.dry_run, a.start)
    return 1 if led.get("error") else 0


if __name__ == "__main__":
    sys.exit(main())
