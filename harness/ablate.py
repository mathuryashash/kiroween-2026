"""
harness/ablate.py - per-hunk ablation analysis.

Given two git revisions of a port, split the diff into hunks and trial each hunk
in isolation on a fast input set to determine which hunks help or hurt which domains.

Usage:
  python -m harness.ablate <name> <before_rev> <after_rev> [--n N] [--seed S]

Outputs plain text and JSON showing per-hunk per-domain effects.
"""

import argparse
import difflib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def get_file_at_rev(name: str, rev: str) -> str:
    """Get routines/<name>.py content at a git revision."""
    rel_path = f"routines/{name}.py"
    r = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", f"{rev}:{rel_path}"],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        raise RuntimeError(f"Cannot read {rel_path} at {rev}: {r.stderr.strip()}")
    return r.stdout


def _groups(before: str, after: str):
    """Change regions with zero context: each is one hunk the agent made."""
    a, b = before.splitlines(keepends=True), after.splitlines(keepends=True)
    return a, b, list(difflib.SequenceMatcher(None, a, b, autojunk=False).get_grouped_opcodes(0))


def split_diff_into_hunks(before: str, after: str) -> list[dict]:
    """Split the change into hunks. Returns [{hunk_id, hunk_text, lines_removed, lines_added}]."""
    a, b, groups = _groups(before, after)
    out = []
    for i, grp in enumerate(groups):
        text, rem, add = [f"@@ line {grp[0][1] + 1} @@\n"], 0, 0
        for tag, i1, i2, j1, j2 in grp:
            for ln in a[i1:i2]:
                text.append("-" + ln if ln.endswith("\n") else "-" + ln + "\n")
                rem += 1
            for ln in b[j1:j2]:
                text.append("+" + ln if ln.endswith("\n") else "+" + ln + "\n")
                add += 1
        out.append({"hunk_id": i, "hunk_text": "".join(text), "lines_removed": rem, "lines_added": add})
    return out


def apply_patch_except_hunk(before: str, after: str, skip_hunk_id: int) -> str:
    """The 'after' file with one hunk put back as it was in 'before'."""
    a, b, groups = _groups(before, after)
    if skip_hunk_id >= len(groups):
        raise ValueError(f"Hunk {skip_hunk_id} out of range (have {len(groups)} hunks)")
    skip = {(op[1], op[2], op[3], op[4]) for op in groups[skip_hunk_id]}
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            out.extend(a[i1:i2])
        elif (i1, i2, j1, j2) in skip:
            out.extend(a[i1:i2])
        else:
            out.extend(b[j1:j2])
    return "".join(out)


def trial_ablation(name: str, code: str, n: int, seed: int) -> dict:
    """Trial a port variant in a temp file. Returns domain_stats."""
    from harness.trial import run_trial
    
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, dir=Path(tempfile.gettempdir())
    ) as tmp:
        tmp.write(code)
        tmp_path = tmp.name
    
    try:
        # We need to point the trial at a custom path
        # run_trial doesn't support custom paths directly, so we'll patch it via
        # environment or by calling the port_runner directly.
        
        # Easier: temporarily overwrite routines/<name>.py, trial it, restore.
        # NO: that would dirty the exam.
        
        # Better: call port_runner directly on the temp file.
        from oracle.referees import make_inputs, get_referee
        import time
        
        ref_info = get_referee(name)
        mpfn = ref_info["mpfn"]
        inputs_by_domain = make_inputs(name, n, seed)
        all_inputs = []
        domain_order = list(inputs_by_domain.keys())
        for d in domain_order:
            all_inputs.extend(inputs_by_domain[d])
        
        t0 = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, "-m", "harness.port_runner", tmp_path, name],
            input="".join(repr(float(x)) + "\n" for x in all_inputs),
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=60,
        )
        wall_time = time.perf_counter() - t0
        
        if proc.returncode != 0:
            return {"error": proc.stderr.strip()[:500], "domain_stats": {}}
        
        lines = [l for l in proc.stdout.splitlines() if l.strip()]
        if len(lines) != len(all_inputs):
            return {"error": f"Expected {len(all_inputs)} outputs, got {len(lines)}", "domain_stats": {}}
        
        got_all = [float(l) for l in lines]
        
        # Compute per-domain stats
        from harness.trial import _domain_stats
        pos = 0
        domain_stats = {}
        for d in domain_order:
            xs = inputs_by_domain[d]
            got = got_all[pos : pos + len(xs)]
            pos += len(xs)
            domain_stats[d] = _domain_stats(xs, got, mpfn, name)
        
        return {"domain_stats": domain_stats, "wall_time_s": wall_time}
    
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def ablate(name: str, before_rev: str, after_rev: str, n: int = 300, seed: int = 1) -> dict:
    """Perform ablation analysis. Returns results dict."""
    before_code = get_file_at_rev(name, before_rev)
    after_code = get_file_at_rev(name, after_rev)
    
    hunks = split_diff_into_hunks(before_code, after_code)
    
    if not hunks:
        return {
            "name": name,
            "before_rev": before_rev,
            "after_rev": after_rev,
            "n": n,
            "seed": seed,
            "hunks": [],
            "message": "No diff between revisions",
        }
    
    # Baseline: trial the full 'after' version, and the 'before' version for context
    baseline = trial_ablation(name, after_code, n, seed)
    previous = trial_ablation(name, before_code, n, seed)
    
    # For each hunk, trial with that hunk reverted
    hunk_results = []
    for hunk in hunks:
        hid = hunk["hunk_id"]
        try:
            reverted_code = apply_patch_except_hunk(before_code, after_code, hid)
            result = trial_ablation(name, reverted_code, n, seed)
            
            # Compare to baseline
            effects = {}
            for domain, stats in result.get("domain_stats", {}).items():
                baseline_pr = baseline.get("domain_stats", {}).get(domain, {}).get("pass_rate", 0.0)
                reverted_pr = stats.get("pass_rate", 0.0)
                delta = reverted_pr - baseline_pr
                
                if abs(delta) < 0.5:
                    effect = "neutral"
                elif delta > 0:
                    effect = f"helped +{delta:.1f}%"
                else:
                    effect = f"hurt {delta:.1f}%"
                
                effects[domain] = {
                    "baseline_pass_rate": baseline_pr,
                    "without_this_hunk_pass_rate": reverted_pr,
                    "delta": delta,
                    "effect": effect,
                }
            
            hunk_results.append({
                "hunk_id": hid,
                "hunk_text": hunk["hunk_text"],
                "lines_removed": hunk["lines_removed"],
                "lines_added": hunk["lines_added"],
                "effects": effects,
                "error": result.get("error"),
            })
        
        except Exception as exc:
            hunk_results.append({
                "hunk_id": hid,
                "hunk_text": hunk["hunk_text"],
                "error": str(exc),
                "effects": {},
            })
    
    return {
        "name": name,
        "before_rev": before_rev,
        "after_rev": after_rev,
        "n": n,
        "seed": seed,
        "baseline": baseline.get("domain_stats", {}),
        "baseline_error": baseline.get("error"),
        "before": previous.get("domain_stats", {}),
        "before_error": previous.get("error"),
        "hunks": hunk_results,
    }


def _rev(r: str) -> str:
    return r[:7] if re.fullmatch(r"[0-9a-f]{40}", r) else r


def format_report(result: dict) -> str:
    """Format ablation results as plain text."""
    lines = [
        f"Ablation analysis: {result['name']} from {_rev(result['before_rev'])} to {_rev(result['after_rev'])}",
        f"  (n={result['n']}, seed={result['seed']})",
        "",
    ]
    
    if "message" in result:
        lines.append(result["message"])
        return "\n".join(lines) + "\n"
    
    before = result.get("before", {})
    if result.get("baseline_error"):
        lines.append(f"The changed version could not be run: {result['baseline_error']}")
    lines.append("Pass rate per sub-domain, before your change -> after it:")
    for domain, stats in result.get("baseline", {}).items():
        b = before.get(domain, {}).get("pass_rate")
        bs = f"{b:6.2f}%" if b is not None else "   n/a "
        lines.append(f"  {domain:12s} {bs} -> {stats.get('pass_rate', 0):6.2f}%")
    
    lines.append("")
    lines.append("Per-hunk effects (what happens when each hunk is reverted):")
    
    for hr in result.get("hunks", []):
        hid = hr["hunk_id"]
        lines.append(f"\nHunk {hid} ({hr.get('lines_removed', 0)}-, {hr.get('lines_added', 0)}+):")
        
        if hr.get("error"):
            lines.append(f"  ERROR: {hr['error']}")
            continue
        
        lines.append(hr["hunk_text"])
        lines.append("  Effects when this hunk is REVERTED:")
        
        for domain, eff in hr.get("effects", {}).items():
            lines.append(
                f"    {domain:12s} baseline {eff['baseline_pass_rate']:6.2f}% "
                f"-> without this hunk {eff['without_this_hunk_pass_rate']:6.2f}% "
                f"({eff['effect']})"
            )
        
        # Summary
        effects_list = [e["effect"] for e in hr.get("effects", {}).values()]
        helped = sum(1 for e in effects_list if "helped" in e)
        hurt = sum(1 for e in effects_list if "hurt" in e)
        
        if hurt > 0 and helped == 0:
            lines.append(f"  -> This hunk HELPS (reverting it hurts {hurt} domain(s))")
        elif helped > 0 and hurt == 0:
            lines.append(f"  -> This hunk HURTS (reverting it helps {helped} domain(s))")
        else:
            lines.append("  -> This hunk is NEUTRAL or MIXED")
    
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ablation analysis for port repairs")
    ap.add_argument("name", help="Routine name")
    ap.add_argument("before_rev", help="Git revision before the change")
    ap.add_argument("after_rev", help="Git revision after the change")
    ap.add_argument("--n", type=int, default=300, help="Number of test inputs (default 300)")
    ap.add_argument("--seed", type=int, default=1, help="RNG seed (default 1)")
    ap.add_argument("--json-out", help="Write JSON output to this file")
    
    args = ap.parse_args(argv)
    
    result = ablate(args.name, args.before_rev, args.after_rev, args.n, args.seed)
    
    # Always print text report
    print(format_report(result))
    
    # Optionally write JSON
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
        print(f"\nJSON written to {args.json_out}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
