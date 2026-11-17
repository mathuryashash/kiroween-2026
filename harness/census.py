"""
harness/census.py - put every original SLATEC routine in the referee map on trial.

For each routine: fetch the Fortran (and its deps) from netlib, compile the original,
run it on the seeded inputs, and record per-domain pass rates against the 50-digit
referee. Optionally the same for the living descendant in SciPy. No port is involved:
this is the screen that decides which routines deserve a resurrection attempt, and it
is run by the harness, not by a person reading code.

Usage: python -m harness.census [--n 1000] [--seed 11] [--only a,b,c]
Writes runs/census/census_<timestamp>.json and prints a table.
"""

import argparse
import json
import math
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def census(names, n, seed, with_scipy=True):
    from harness.fetch import fetch_all_deps
    from harness.trial import run_trial
    from oracle.referees import HAND_TOUCHED, SCIPY_MAP

    rows = []
    for name in names:
        row = {"name": name, "hand_touched": name in HAND_TOUCHED}
        t0 = time.perf_counter()
        try:
            fetch_all_deps(name)
            r = run_trial(name, "original", n, seed)
            row["original"] = {d: {"pass_rate": round(s["pass_rate"], 2), "max_ulp": s["max_ulp"],
                                   "worst_x": s["worst_x"]} for d, s in r["domain_stats"].items()}
            row["original_overall"] = r["overall_pass_rate"]
            row["min_domain_pass"] = min(s["pass_rate"] for s in r["domain_stats"].values())
            if with_scipy and name in SCIPY_MAP:
                s = run_trial(name, "scipy", n, seed)
                row["scipy"] = {d: {"pass_rate": round(v["pass_rate"], 2), "max_ulp": v["max_ulp"]}
                                for d, v in s["domain_stats"].items()}
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"[:600]
            row["trace"] = traceback.format_exc()[-1500:]
        row["seconds"] = round(time.perf_counter() - t0, 1)
        rows.append(row)
        _print_row(row)
    return rows


def _fmt_ulp(u):
    try:
        u = float(u)
    except (TypeError, ValueError):
        return str(u)
    if math.isinf(u):
        return "inf"
    return f"{u:.3g}"


def _print_row(row):
    if "error" in row:
        print(f"{row['name']:8s} ERROR {row['error'][:150]}", flush=True)
        return
    worst = min(row["original"].items(), key=lambda kv: kv[1]["pass_rate"])
    top = max(row["original"].items(), key=lambda kv: float(kv[1]["max_ulp"]))
    flag = "  <-- original fails a domain" if row["min_domain_pass"] < 95.0 else ""
    hand = " (hand-touched)" if row["hand_touched"] else ""
    sp = ""
    if "scipy" in row:
        smin = min(v["pass_rate"] for v in row["scipy"].values())
        sp = f"  scipy worst {smin:6.2f}%"
    print(f"{row['name']:8s} overall {row['original_overall']:6.2f}%  worst-pass {worst[0]:10s} "
          f"{worst[1]['pass_rate']:6.2f}%  largest error {top[0]} {_fmt_ulp(top[1]['max_ulp'])} ULP"
          f"{sp}{hand}{flag}  [{row['seconds']}s]", flush=True)


def main(argv=None) -> int:
    from oracle.referees import REFEREES

    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--only")
    ap.add_argument("--no-scipy", action="store_true")
    a = ap.parse_args(argv)
    names = a.only.split(",") if a.only else list(REFEREES)
    rows = census(names, a.n, a.seed, with_scipy=not a.no_scipy)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = REPO_ROOT / "runs" / "census" / f"census_{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)

    def _j(o):
        if isinstance(o, float) and not math.isfinite(o):
            return str(o)
        if isinstance(o, dict):
            return {k: _j(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_j(v) for v in o]
        return o

    out.write_text(json.dumps(_j({"n": a.n, "seed": a.seed, "rows": rows}), indent=2),
                   encoding="utf-8", newline="\n")
    print(f"\nwritten {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
