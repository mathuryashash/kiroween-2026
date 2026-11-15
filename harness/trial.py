"""
harness/trial.py – the GALVANI exam CLI.

Usage:
  python -m harness.trial <name> --impl original|fixed-original|port|scipy
                                 --n N --seed S

Writes runs/<name>/<impl>_<UTCstamp>.json
Writes runs/<name>/latest.json (index of newest run per impl)

spec steps 4-10.
"""

import argparse
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import mpmath
import numpy as np

mpmath.mp.dps = 50

REPO_ROOT = Path(__file__).parent.parent
RUNS_DIR  = REPO_ROOT / "runs"


# ---------------------------------------------------------------------------
# Toolchain info
# ---------------------------------------------------------------------------

def _python_ver() -> str:
    return f"{sys.version.splitlines()[0]}"

def _numpy_ver() -> str:
    return np.__version__

def _mpmath_ver() -> str:
    return mpmath.__version__

def _scipy_ver() -> str:
    try:
        import scipy
        return scipy.__version__
    except ImportError:
        return "not installed"

def _git_commit() -> str:
    try:
        r = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10
        )
        return r.stdout.strip()
    except Exception:
        return "unknown"


EXAM_PATHS = ["harness", "oracle", "tests", "fortran", "tools",
              ".kiro/steering", ".kiro/agents", ".kiro/hooks"]


def _exam_dirty() -> list[str]:
    """Exam files that differ from the committed tree (modified, deleted or untracked).

    A port trial with a non-empty list is VOID: nobody (agent or human) may change
    the exam and the answer in the same uncommitted state.
    """
    r = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "status", "--porcelain", "--untracked-files=all", "--", *EXAM_PATHS],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        return [f"git status failed: {r.stderr.strip()[:200]}"]
    return [line[3:] for line in r.stdout.splitlines() if line.strip()]


def _file_sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _manifest() -> dict:
    """sha256 of every harness, oracle, fortran file used."""
    manifest = {}
    for root_rel in ["harness", "oracle", "fortran"]:
        root = REPO_ROOT / root_rel
        if not root.exists():
            continue
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix in (".py", ".f", ".f90", ".md"):
                rel = str(p.relative_to(REPO_ROOT)).replace("\\", "/")
                manifest[rel] = _file_sha256(str(p))
    return manifest


# ---------------------------------------------------------------------------
# Per-domain stats
# ---------------------------------------------------------------------------

def _domain_stats(
    xs: list[float],
    got: list[float],
    mpfn,
    name: str,
) -> dict:
    from harness.ulp import ulp_error, allowed_ulp

    errors = []
    pass_count = 0

    for x, g in zip(xs, got):
        try:
            ref_mp = mpfn(mpmath.mpf(x))
            ref = float(ref_mp)
        except Exception:
            continue

        err = ulp_error(g, ref)
        allow = allowed_ulp(name, x)
        passed = math.isfinite(err) and err <= allow
        if passed:
            pass_count += 1
        errors.append((x, err, allow, passed))

    if not errors:
        return {
            "n": 0,
            "pass_rate": 0.0,
            "max_ulp": float("inf"),
            "median_ulp": float("inf"),
            "p99_ulp": float("inf"),
            "worst_x": None,
        }

    n = len(errors)
    errs = [e[1] for e in errors]
    finite_errs = [e for e in errs if math.isfinite(e)]

    max_ulp   = max(errs)
    worst_x   = errors[errs.index(max_ulp)][0]
    median_ulp = statistics.median(finite_errs) if finite_errs else float("inf")
    p99_ulp    = float(np.percentile(finite_errs, 99)) if finite_errs else float("inf")

    return {
        "n": n,
        "pass_rate": pass_count / n * 100.0,
        "max_ulp": max_ulp,
        "median_ulp": median_ulp,
        "p99_ulp": p99_ulp,
        "worst_x": worst_x,
    }


# ---------------------------------------------------------------------------
# Main trial runner
# ---------------------------------------------------------------------------

def run_trial(
    name: str,
    impl: str,
    n: int,
    seed: int,
    gfortran_exe: str | None = None,
) -> dict:
    from oracle.referees import make_inputs, get_referee, SCIPY_MAP
    from harness.verdict import compute_verdict

    ref_info = get_referee(name)
    mpfn     = ref_info["mpfn"]
    inputs_by_domain = make_inputs(name, n, seed)
    all_inputs = []
    domain_order = list(inputs_by_domain.keys())
    for d in domain_order:
        all_inputs.extend(inputs_by_domain[d])

    # --- Run the implementation ---
    if impl == "port":
        port_path = str(REPO_ROOT / "routines" / f"{name}.py")
        t0 = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, "-m", "harness.port_runner", port_path, name],
            input="".join(repr(float(x)) + "\n" for x in all_inputs),
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=600,
        )
        wall_time = time.perf_counter() - t0
        if proc.returncode != 0:
            return {
                "verdict": "DISQUALIFIED",
                "error": (proc.stderr.strip() or f"port runner exit {proc.returncode}")[-2000:],
                "impl": impl,
                "name": name,
            }
        lines = [l for l in proc.stdout.splitlines() if l.strip()]
        if len(lines) != len(all_inputs):
            raise RuntimeError(
                f"port runner returned {len(lines)} values for {len(all_inputs)} inputs"
            )
        got_all = [float(l) for l in lines]
        fc_ver = "N/A (port)"

    elif impl == "scipy":
        if name not in SCIPY_MAP:
            raise ValueError(f"No scipy mapping for {name}")
        scipy_fn = SCIPY_MAP[name]
        t0 = time.perf_counter()
        got_all = [float(scipy_fn(x)) for x in all_inputs]
        wall_time = time.perf_counter() - t0
        fc_ver = "N/A (scipy)"

    else:
        # Fortran: original or fixed-original
        from harness.driver import build_driver, run_batch, find_gfortran, VARIANTS_DIR, SLATEC_DIR
        fc = gfortran_exe or find_gfortran()

        variant_f = None
        if impl == "fixed-original":
            variant_f = str(VARIANTS_DIR / f"{name}_fixed.f")

        exe, fc_ver = build_driver(name, variant_f=variant_f)
        got_all, wall_time = run_batch(exe, all_inputs)

    # --- Per-domain stats ---
    pos = 0
    domain_stats = {}
    for d in domain_order:
        xs = inputs_by_domain[d]
        got = got_all[pos : pos + len(xs)]
        pos += len(xs)
        domain_stats[d] = _domain_stats(xs, got, mpfn, name)

    overall_pass = sum(s["pass_rate"] * s["n"] for s in domain_stats.values())
    overall_n    = sum(s["n"] for s in domain_stats.values())
    overall_pass_rate = overall_pass / overall_n if overall_n else 0.0

    # A port is judged against the original on the SAME inputs (same n, seed),
    # so HEALED can be awarded; other impls get a plain verdict.
    original_summary = None
    exam_dirty: list[str] = []
    if impl == "port":
        orig = run_trial(name, "original", n, seed, gfortran_exe=gfortran_exe)
        original_summary = {
            d: {"pass_rate": s["pass_rate"], "max_ulp": s["max_ulp"]}
            for d, s in orig["domain_stats"].items()
        }
        verdict = compute_verdict(domain_stats, original_stats=orig["domain_stats"])
        # Integrity: the exam must be exactly what is committed, or the run is void.
        exam_dirty = _exam_dirty()
        if exam_dirty:
            verdict = "VOID"
    else:
        verdict = compute_verdict(domain_stats, original_stats=None)

    # --- Assemble result ---
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result = {
        "name":       name,
        "impl":       impl,
        "timestamp":  stamp,
        "n_total":    len(all_inputs),
        "wall_time_s": round(wall_time, 4),
        "toolchain": {
            "gfortran":  fc_ver,
            "python":    _python_ver(),
            "numpy":     _numpy_ver(),
            "mpmath":    _mpmath_ver(),
            "scipy":     _scipy_ver(),
        },
        "git_commit": _git_commit(),
        "manifest":   _manifest(),
        "inputs_spec": {
            "seed": seed,
            "n":    n,
            "domains": {
                d: {"n": len(xs), "lo": min(xs), "hi": max(xs)}
                for d, xs in inputs_by_domain.items()
            },
        },
        "domain_stats":   domain_stats,
        "overall_pass_rate": round(overall_pass_rate, 4),
        "verdict":    verdict,
    }
    if impl == "port":
        result["original_on_same_inputs"] = original_summary
        result["exam_dirty_files"] = exam_dirty
    return result


# ---------------------------------------------------------------------------
# Write runs/ output
# ---------------------------------------------------------------------------

def write_run(name: str, impl: str, result: dict) -> Path:
    run_dir = RUNS_DIR / name
    run_dir.mkdir(parents=True, exist_ok=True)

    stamp = result.get("timestamp", datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    impl_slug = impl.replace("-", "_")
    out_path = run_dir / f"{impl_slug}_{stamp}.json"

    # Serialise: replace inf/nan with strings for JSON
    def _jsonify(obj):
        if isinstance(obj, float):
            if math.isnan(obj):  return "NaN"
            if math.isinf(obj):  return "Inf"
            return obj
        if isinstance(obj, dict):
            return {k: _jsonify(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_jsonify(v) for v in obj]
        return obj

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(_jsonify(result), fh, indent=2)

    # Update latest.json
    latest_path = run_dir / "latest.json"
    if latest_path.exists():
        with open(latest_path, encoding="utf-8") as fh:
            latest = json.load(fh)
    else:
        latest = {}
    latest[impl] = str(out_path.name)
    with open(latest_path, "w", encoding="utf-8") as fh:
        json.dump(latest, fh, indent=2)

    return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="GALVANI trial CLI")
    parser.add_argument("name", help="Routine name, e.g. dgamma")
    parser.add_argument("--impl", required=True,
                        choices=["original", "fixed-original", "port", "scipy"])
    parser.add_argument("--n", type=int, default=2000, help="Total number of test inputs")
    parser.add_argument("--seed", type=int, default=1, help="RNG seed")
    args = parser.parse_args()

    print(f"[trial] {args.name} --impl {args.impl} --n {args.n} --seed {args.seed}")

    result = run_trial(args.name, args.impl, args.n, args.seed)
    out_path = write_run(args.name, args.impl, result)

    print(f"\n[trial] written to {out_path}")
    print(f"[trial] verdict: {result.get('verdict','?')}")
    print(f"[trial] overall pass rate: {result.get('overall_pass_rate','?'):.2f}%")
    print(f"[trial] wall time: {result.get('wall_time_s','?'):.4f}s")
    print("\nPer-domain stats:")
    for d, s in result.get("domain_stats", {}).items():
        max_u = s.get("max_ulp", "?")
        wx    = s.get("worst_x", "?")
        pr    = s.get("pass_rate", "?")
        print(f"  {d:12s}  pass={pr:6.1f}%  max_ulp={max_u:>14}  worst_x={wx}")


if __name__ == "__main__":
    main()
