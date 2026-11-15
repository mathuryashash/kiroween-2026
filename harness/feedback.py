"""
harness/feedback.py - turn a port trial JSON into the plain-text report the agent sees.

The resurrector cannot read runs/ (sealed exam), so the orchestrator passes this
text in the next prompt. It contains only what a reviewer would tell a human porter:
per-domain pass rates for the port and for the compiled original on the SAME inputs,
and the worst input of each failing domain with the port's value and the 50-digit
reference. It never contains a fix.

Usage: python -m harness.feedback runs/<name>/port_<ts>.json [--out file]
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import mpmath

from oracle.referees import get_referee

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_port(name: str):
    path = REPO_ROOT / "routines" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_fb_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, name)


def build_feedback(run: dict) -> str:
    name = run["name"]
    ref = get_referee(name)
    mpfn = ref["mpfn"]
    orig = run.get("original_on_same_inputs") or {}
    lines = [
        f"GALVANI trial report for routines/{name}.py "
        f"(run {run['timestamp']}, n={run['n_total']}, commit {run.get('git_commit', '?')[:7]})",
        "",
        f"Verdict: {run['verdict']} (overall pass rate {run['overall_pass_rate']:.2f}%).",
        "Per sub-domain, pass = within the allowed ULP error for that input:",
        "",
    ]
    identical = True
    for d, s in run["domain_stats"].items():
        line = f"  {d:9s} port: pass {s['pass_rate']:6.2f}%  max_ulp {s['max_ulp']:.0f}"
        if d in orig:
            o = orig[d]
            line += f"   | compiled original, same inputs: pass {o['pass_rate']:6.2f}%  max_ulp {o['max_ulp']:.0f}"
            identical &= (o["pass_rate"] == s["pass_rate"] and o["max_ulp"] == s["max_ulp"])
        lines.append(line)
    if orig and identical:
        lines += ["", "The port matches the compiled original on every sub-domain, so the "
                      "translation looks faithful; the failures come from the original algorithm."]
    fn = _load_port(name)
    failing = [(d, s) for d, s in run["domain_stats"].items() if s["pass_rate"] < 99.0]
    if failing:
        lines += ["", "Worst input in each failing sub-domain (x, your value, 50-digit reference):"]
        for d, s in failing:
            x = s["worst_x"]
            try:
                got = repr(float(fn(x)))
            except Exception as exc:
                got = f"raised {type(exc).__name__}"
            refv = repr(float(mpfn(mpmath.mpf(x))))
            lines.append(f"  {d:9s} {x!r:26s} {got:24s} {refv}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_json")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    run = json.loads(Path(a.run_json).read_text(encoding="utf-8"))
    text = build_feedback(run)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
