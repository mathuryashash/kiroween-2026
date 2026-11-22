#!/usr/bin/env python3
"""
site/tools/build.py - build the static GALVANI site into site/public/ (git-ignored output).

Every number on the site comes from run files that are committed in git; the build refuses
VOID runs, runs taken on a dirty exam, and run files with uncommitted changes. The build writes
site/public/data/ledger.json (with provenance per number), copies index.html and Kiro's port
source for the in-browser re-run, and stamps the commit the site was built from.

  python site/tools/build.py            # build
  python site/tools/build.py --check    # build into a temp dir and verify, write nothing
"""
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SITE = REPO / "site"
OUT = SITE / "public"
GH = "https://github.com/mathuryashash/kiroween-2026"

# The routines shown on the site, with the committed runs that carry their numbers.
# A routine is listed only once a pipeline run supports it; each entry names its run files.
ENTRIES = [
    {
        "name": "dgamma",
        "title": "DGAMMA, the gamma function",
        "mp_fn": "gamma",
        "fortran_lines": [117, 119], "bug_lines": [118],
        "fix_marker": "x + (i - 1)", "port_window": [3, 1],
        "flaw": ("For tiny x the loop computes X+I-1 as (x + 1) - 1, which throws away most of x's "
                 "digits just before dividing by it."),
        "port_dev_run": "runs/dgamma/port_20261117T191537Z.json",
        "port_heldout_run": "runs/dgamma/port_20261117T191545Z.json",
        "story_commits": ["f5f2b74", "f8a0aac", "6fa4d7f", "9303c19", "69b4bc4", "9641f48", "11f56e0", "f933cca"],
        "faithful_commit": "f5f2b74",   # its trial (f8a0aac): identical to the compiled original
        "samples": [1e-12, 1.0446107243801513e-12, 3e-7, 0.0011511239380811596, 0.5,
                    5.5, -1.1172030363697255e-06, -2.5],
        "how": "hand-run",
        "disclosure": ("Healed with a hand-run version of the loop. The autopsy tool was built after "
                       "the bug's location was known, so DGAMMA is not a cold find."),
    },
    {
        "name": "dcot",
        "title": "DCOT, the cotangent",
        "mp_fn": "cot",
        "fortran_lines": [89, 93], "bug_lines": [90, 91],
        "fix_marker": "if y > 0.0:", "port_window": [4, 4],
        "flaw": ("Near a multiple of pi the reduced argument is tiny, and the code falls back to 1/X: "
                 "the right answer near x = 0, but not near pi, 2 pi, ..."),
        "port_dev_run": "runs/dcot/port_20261117T193732Z.json",
        "port_heldout_run": "runs/dcot/port_20261117T193736Z.json",
        "story_commits": ["6f1fd63", "8158fb3", "1b1a535", "45219eb", "e96d3b7", "b84a9f5",
                          "f537f86", "ccc4ef7", "458ad01", "50dc03f"],
        "faithful_commit": "e96d3b7",   # its trial (34a9937): identical to the compiled original
        "samples": [3.141592653706479, 3.14159265, 6.2831853, -3.1415926535, 3.1416, 100.0, 1.0],
        "how": "loop",
        "disclosure": ("Healed by the one-command loop (python -m harness.loop dcot). Three generic "
                       "fixes to the loop were made while watching earlier DCOT runs fail, so DCOT is "
                       "not a cold test either. Every run, failed ones included, is in the history."),
    },
    {
        "name": "dpsi",
        "title": "DPSI, the digamma function",
        "mp_fn": "digamma",
        "fortran_lines": [140, 142], "bug_lines": [141],
        "fix_marker": "x + (i - 1)", "port_window": [3, 1],
        "flaw": ("For x near zero, on either side, the loop computes X+I-1 as (x + 1) - 1, the same slip "
                 "as in DGAMMA, which throws away most of x's digits just before dividing by it."),
        "port_dev_run": "runs/dpsi/port_20261122T035246Z.json",
        "port_heldout_run": "runs/dpsi/port_20261122T035306Z.json",
        "story_commits": ["3a2c1bd", "7a63326", "cfcaa58", "7349dcd", "d7ec522", "4c0b2e5", "ba04301",
                          "0236ed6", "76664c1", "845953f", "2d9f682", "5a00da9", "8c41a19"],
        "faithful_commit": "3a2c1bd",   # its trial (7a63326): identical to the compiled original
        "samples": [1.187877702770561e-10, 1e-7, 0.001, 0.3, 2.5, -1.0025739519280612e-06, -0.0001, -2.3],
        "how": "loop",
        "how_label": "healed by the one-command loop, on its second cold run",
        # The road from STILL DEAD to HEALED, read from committed ledgers.
        "attempts": [
            {"ledger": "runs/ledger/dpsi_20261117T193921Z.json",
             "note": ("Round 1 made two ranges worse and the loop undid it. Round 2 changed nothing useful "
                      "and was undone too; Kiro wrote that the failures were \"inherent to the original\". "
                      "The autopsy had already pointed at line 265, x + i - 1.")},
            {"between": ("Nothing in the exam or the loop changed: the exam is identical to tag "
                         "loop-frozen-1, and Kiro's first prompt was the same text in both runs apart from the "
                         "commit hash. Only the model changed, from claude-haiku-4.5 to claude-sonnet-4.5, "
                         "following the plan from the first day: start every routine on Haiku and move up "
                         "only when Haiku gets stuck.")},
            {"ledger": "runs/ledger/dpsi_20261122T035153Z.json",
             "note": ("One round. Kiro read only routines/dpsi.py, changed line 265 to x + (i - 1) and also "
                      "rewrote the reflection line. The held-out trial agreed.")},
        ],
        "ablation": "runs/dpsi/ablate_20261122T035821Z.json",
        "disclosure": ("Cold run 1 failed and stays in the history. Retrying on a bigger model was my call, "
                       "made after seeing it fail; the loop and the exam were not touched. DPSI's flaw is the "
                       "same pattern as DGAMMA's, so it is a weaker test of generality than a new kind of bug."),
    },
]


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                          check=True).stdout.strip()


def committed_json(rel: str) -> tuple[dict, str]:
    """Load a run file and return it with the commit that added it; refuse anything uncommitted."""
    if git("status", "--porcelain", "--", rel):
        raise SystemExit(f"refusing {rel}: uncommitted changes")
    commit = git("log", "-1", "--format=%H", "--", rel)
    if not commit:
        raise SystemExit(f"refusing {rel}: not in git")
    data = json.loads((REPO / rel).read_text(encoding="utf-8"))
    if data.get("verdict") == "VOID":
        raise SystemExit(f"refusing {rel}: VOID run")
    if data.get("exam_dirty_files"):
        raise SystemExit(f"refusing {rel}: taken on a dirty exam {data['exam_dirty_files'][:3]}")
    return data, commit


def _num(v):
    return v if isinstance(v, (int, float)) else None


def domains(run: dict) -> dict:
    return {d: {"n": s.get("n"), "pass_rate": _num(s.get("pass_rate")), "max_ulp": _num(s.get("max_ulp")),
                "median_ulp": _num(s.get("median_ulp")), "worst_x": _num(s.get("worst_x"))}
            for d, s in run["domain_stats"].items()}


def entry_data(e: dict) -> dict:
    out = {k: e[k] for k in ("name", "title", "flaw", "disclosure", "how", "mp_fn", "bug_lines")}
    out["how_label"] = e.get("how_label")
    out["attempts"] = [attempt_data(a) for a in e.get("attempts", [])]
    out["ablation"] = ablation_data(e["ablation"]) if e.get("ablation") else None
    out["runs"] = {}
    src = (REPO / "fortran" / "slatec" / f"{e['name']}.f").read_text(encoding="utf-8", errors="replace").splitlines()
    a, b = e["fortran_lines"]
    out["fortran_excerpt"] = [[n, src[n - 1].rstrip()] for n in range(a, b + 1)]
    for key in ("port_dev_run", "port_heldout_run"):
        run, commit = committed_json(e[key])
        out["runs"][key.replace("_run", "")] = {
            "verdict": run["verdict"], "overall_pass_rate": run["overall_pass_rate"],
            "n": run.get("n_total"), "seed": (run.get("inputs_spec") or {}).get("seed"),
            "domains": domains(run), "file": e[key], "commit": commit,
            "url": f"{GH}/blob/{commit}/{e[key]}",
            "original_on_same_inputs": run.get("original_on_same_inputs"),
        }
    story = []
    for c in e["story_commits"]:
        full, date, subject = git("show", "-s", "--format=%H%x1f%aI%x1f%s", c).split("\x1f")
        story.append({"commit": full, "date": date, "subject": subject, "url": f"{GH}/commit/{full}"})
    out["story"] = story
    out["samples"] = samples(e)
    out["faithful_commit"] = git("rev-parse", e["faithful_commit"])
    out["faithful_source"] = git("show", f"{e['faithful_commit']}:routines/{e['name']}.py")
    out["port_source"] = (REPO / "routines" / f"{e['name']}.py").read_text(encoding="utf-8")
    rel = f"routines/{e['name']}.py"
    if git("status", "--porcelain", "--", rel):
        raise SystemExit(f"refusing {rel}: uncommitted changes")
    out["port_commit"] = git("log", "-1", "--format=%H", "--", rel)
    lines = (REPO / rel).read_text(encoding="utf-8").splitlines()
    fix = next((i for i, ln in enumerate(lines, 1) if e["fix_marker"] in ln), None)
    if fix is None:
        raise SystemExit(f"{rel}: fixed line not found")
    out["port_line"] = fix
    before, after = e["port_window"]
    out["port_excerpt"] = [[n, lines[n - 1]] for n in range(max(1, fix - before), min(len(lines), fix + after) + 1)]
    return out


def attempt_data(a: dict) -> dict:
    """One step of a routine's road to its verdict: a committed loop ledger, or a note between runs."""
    if "between" in a:
        return {"between": a["between"]}
    led, commit = committed_json(a["ledger"])
    rounds = [{"round": r.get("round"), "type": r.get("type"), "credits": r.get("credits"),
               "trial_after": r.get("trial_after"), "regressions": r.get("regressions"),
               "commit": r.get("commit"), "undo_commit": r.get("undo_commit")} for r in led["rounds"]]
    return {"file": a["ledger"], "url": f"{GH}/blob/{commit}/{a['ledger']}", "model": led["model"],
            "run_id": led["run_id"], "credits": led["total_credits"], "stop_reason": led["stop_reason"],
            "result": led.get("result") or (led.get("final_dev_trial") or "").split(",")[0] or None,
            "rounds": rounds, "note": a.get("note", "")}


def ablation_data(rel: str) -> dict:
    """Which edit of the healing round did the work: each code hunk reverted on its own."""
    data, commit = committed_json(rel)
    hunks = []
    for h in data["hunks"]:
        lines = [ln for ln in h["hunk_text"].splitlines()[1:] if ln[:1] in "+-"]
        code = [ln for ln in lines if not ln[1:].strip().startswith("#")]
        if not code:
            continue                                   # comment-only hunk
        hurt = {d: [s["baseline_pass_rate"], s["without_this_hunk_pass_rate"]]
                for d, s in h["effects"].items() if s["delta"] < 0}
        pad = min(len(ln[1:]) - len(ln[1:].lstrip()) for ln in code)
        hunks.append({"code": [ln[0] + " " + ln[1 + pad:] for ln in code], "hurt_without": hurt})
    return {"file": rel, "url": f"{GH}/blob/{commit}/{rel}", "n": data["n"], "seed": data["seed"],
            "hunks": hunks}


def _load(name: str, src: str):
    import types
    mod = types.ModuleType(name)
    exec(compile(src, name, "exec"), mod.__dict__)
    return getattr(mod, name.split("_")[0])


def samples(e: dict) -> list:
    """Faithful port vs healed port vs the 50-digit referee on a few inputs, computed at build time.

    The faithful port is Kiro's translation before healing; its trial matched the compiled
    original on every sub-domain, so it stands in for the original (which needs a compiler)."""
    sys.path.insert(0, str(REPO))
    import mpmath
    from harness.ulp import allowed_ulp, ulp_error
    from oracle.referees import get_referee
    blind = _load(e["name"] + "_faithful", git("show", f"{e['faithful_commit']}:routines/{e['name']}.py"))
    healed = _load(e["name"] + "_healed", (REPO / "routines" / f"{e['name']}.py").read_text(encoding="utf-8"))
    mpfn = get_referee(e["name"])["mpfn"]
    rows = []
    for x in e["samples"]:
        with mpmath.workdps(50):
            ref = float(mpfn(mpmath.mpf(x)))
        b, h = blind(x), healed(x)
        rows.append({"x": x, "referee": ref, "faithful": b, "healed": h, "allowed": allowed_ulp(e["name"], x),
                     "faithful_ulp": ulp_error(b, ref), "healed_ulp": ulp_error(h, ref)})
    return rows


CENSUS_NOTES = {"dgamr": "calls DGAMMA; passes when linked to the fixed DGAMMA",
                "dlngam": "calls DGAMMA; passes when linked to the fixed DGAMMA",
                "derf": "already known: reported publicly in 2012",
                "dpsi": "cold run 1 failed;"}


def census_summary() -> dict | None:
    """Merge the census files in time order; a later file updates the rows it re-ran."""
    files = sorted((REPO / "runs" / "census").glob("census_*.json"))
    if not files:
        return None
    rows, used, sizes = {}, [], set()
    for f in files:
        rel = str(f.relative_to(REPO)).replace("\\", "/")
        committed_json_plain(rel)
        census = json.loads(f.read_text(encoding="utf-8"))
        sizes.add((census["n"], census["seed"]))
        for r in census["rows"]:
            if "original" in r:
                rows[r["name"]] = r
        used.append(rel)
    failing = []
    for name, r in sorted(rows.items()):
        if r.get("min_domain_pass", 100) < 95:
            worst = min(r["original"].items(), key=lambda kv: kv[1]["pass_rate"])
            failing.append({"name": name, "domain": worst[0], "pass_rate": worst[1]["pass_rate"],
                            "max_ulp": worst[1]["max_ulp"], "note": CENSUS_NOTES.get(name, "")})
    if len(sizes) != 1:
        raise SystemExit(f"census files use different input sets: {sizes}")
    (n, seed), = sizes
    return {"files": used, "routines": len(rows), "n": n, "seed": seed, "failing": failing}


def committed_json_plain(rel: str) -> None:
    if git("status", "--porcelain", "--", rel) or not git("log", "-1", "--format=%H", "--", rel):
        raise SystemExit(f"refusing {rel}: not committed")


def _clean(v):
    """JSON has no inf/nan: write them as strings the page can show."""
    if isinstance(v, float) and not math.isfinite(v):
        return "inf" if v > 0 else ("-inf" if v < 0 else "nan")
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    return v


def build(out: Path) -> dict:
    if out.exists():
        shutil.rmtree(out)
    (out / "data").mkdir(parents=True)
    head = git("rev-parse", "HEAD")
    ledger = {"built_from": head, "built_from_url": f"{GH}/tree/{head}", "repo": GH,
              "routines": [entry_data(e) for e in ENTRIES]}
    ledger["census"] = census_summary()
    text = json.dumps(_clean(ledger), separators=(",", ":"), allow_nan=False, default=str)
    (out / "data" / "ledger.json").write_text(text, encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    # The ledger is also inlined, so the page needs no fetch to show its numbers.
    page = (SITE / "index.html").read_text(encoding="utf-8")
    if "__LEDGER_JSON__" not in page:
        raise SystemExit("site/index.html has no __LEDGER_JSON__ placeholder")
    page = page.replace("__LEDGER_JSON__", text.replace("</", "<\\/"))
    (out / "index.html").write_text(page, encoding="utf-8")
    return ledger


def main() -> int:
    if "--check" in sys.argv:
        with tempfile.TemporaryDirectory() as tmp:
            led = build(Path(tmp) / "public")
        print(f"check ok: {len(led['routines'])} routine(s), built from {led['built_from'][:7]}")
        return 0
    led = build(OUT)
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"built site/public ({size / 1024:.1f} KB) from {led['built_from'][:7]}: "
          + ", ".join(r["name"] for r in led["routines"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
