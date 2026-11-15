"""
harness/autopsy.py - locate the line and operation where a port loses precision.

Shadow-value tracing. The port runs twice on one input: once in IEEE double, as
shipped, and once as the SAME code with every value carried in 60-digit mpmath
arithmetic (the "shadow"). A line tracer snapshots every local at every line in both
runs. Aligning the two traces gives, for each line executed, how far each double
value has drifted from its shadow, in ULPs. The first line where a value goes bad
is then re-evaluated sub-expression by sub-expression in both modes, which shows
which single operation lost the digits.

Scope, stated plainly: this measures ROUNDING error of the algorithm as written
(the shadow runs the same algorithm, including its truncated series). It does not
measure approximation error, and it never proposes a fix. It is generic: it works
for any routines/<name>.py that imports only math.

Usage: python -m harness.autopsy <name> <x> [<x> ...]
"""

import ast
import importlib.util
import math
import os
import sys
from pathlib import Path

import mpmath

REPO_ROOT = Path(__file__).resolve().parent.parent
SHADOW_DPS = 60
BAD_ULP = 16.0          # a value is "bad" when double and shadow differ by more than this
MAX_DEPTH = 3           # how far to drill into helper calls


# --------------------------------------------------------------------------- shadow math
def _mp_floor(v):
    return int(mpmath.floor(v))


def _mp_ceil(v):
    return int(mpmath.ceil(v))


def _mp_copysign(a, b):
    a = mpmath.fabs(a)
    return -a if (b < 0 or (b == 0 and math.copysign(1.0, float(b)) < 0)) else a


_MP_FUNCS = {
    "exp": mpmath.exp, "log": mpmath.log, "log10": mpmath.log10, "log2": lambda v: mpmath.log(v, 2),
    "log1p": mpmath.log1p, "expm1": mpmath.expm1, "sqrt": mpmath.sqrt, "pow": mpmath.power,
    "sin": mpmath.sin, "cos": mpmath.cos, "tan": mpmath.tan, "asin": mpmath.asin,
    "acos": mpmath.acos, "atan": mpmath.atan, "atan2": mpmath.atan2, "sinh": mpmath.sinh,
    "cosh": mpmath.cosh, "tanh": mpmath.tanh, "hypot": mpmath.hypot, "fabs": mpmath.fabs,
    "floor": _mp_floor, "ceil": _mp_ceil, "copysign": _mp_copysign,
    "isnan": mpmath.isnan, "isinf": mpmath.isinf, "isfinite": mpmath.isfinite,
    "gamma": mpmath.gamma, "lgamma": mpmath.loggamma, "erf": mpmath.erf, "erfc": mpmath.erfc,
}
_MP_CONSTS = {"pi": lambda: +mpmath.pi, "e": lambda: +mpmath.e, "tau": lambda: 2 * mpmath.pi,
              "inf": lambda: mpmath.inf, "nan": lambda: mpmath.nan}


class _MathShim:
    """Stands in for the math module in the shadow run."""

    def __getattr__(self, name):
        if name in _MP_FUNCS:
            return _MP_FUNCS[name]
        if name in _MP_CONSTS:
            return _MP_CONSTS[name]()
        return getattr(math, name)          # anything else stays double precision


_SHIM = _MathShim()


def _mp_float(v=0.0):
    """float() in the shadow run: keep full precision instead of rounding to double."""
    return mpmath.mpf(v.strip() if isinstance(v, str) else v)


def _load(path: Path, name: str, shadow: bool):
    tag = "s" if shadow else "d"
    spec = importlib.util.spec_from_file_location(f"_autopsy_{tag}_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    if shadow:
        mod.__dict__["float"] = _mp_float
    spec.loader.exec_module(mod)
    if shadow:
        for k, v in list(vars(mod).items()):
            if v is math:
                setattr(mod, k, _SHIM)
            elif callable(v) and getattr(v, "__module__", None) == "math":
                setattr(mod, k, getattr(_SHIM, v.__name__))
    return mod


# --------------------------------------------------------------------------- tracing
def _is_real(v) -> bool:
    return isinstance(v, (float, mpmath.mpf)) and not isinstance(v, bool)


def _trace(fn, arg, path: str):
    """Run fn(arg) under a line tracer. Returns (events, calls).

    events: list of (k, func, lineno, event, locals_copy, retval)
    calls:  {k: (parent_k, global_event_index_at_call)}
    """
    target = os.path.normcase(os.path.abspath(path))
    events, calls, ids = [], {}, {}

    def local(frame, event, a):
        if event in ("line", "return"):
            events.append((ids[id(frame)], frame.f_code.co_name, frame.f_lineno, event,
                           dict(frame.f_locals), a if event == "return" else None))
        return local

    def glob(frame, event, a):
        if event == "call" and os.path.normcase(os.path.abspath(frame.f_code.co_filename)) == target:
            k = len(calls)
            ids[id(frame)] = k
            calls[k] = (ids.get(id(frame.f_back)), len(events))
            return local
        return None

    sys.settrace(glob)
    try:
        result = fn(arg)
    except Exception as exc:                 # the trace up to the failure is still useful
        result = exc
    finally:
        sys.settrace(None)
    return events, calls, result


def ulp_diff(d, s) -> float:
    """ULP distance between a double-run value and its shadow value."""
    try:
        fd = float(d)
    except (TypeError, ValueError, OverflowError):
        return math.inf
    if math.isnan(fd) or mpmath.isnan(s):
        return 0.0 if (math.isnan(fd) and mpmath.isnan(s)) else math.inf
    try:
        sf = float(s)
    except OverflowError:
        return math.inf
    if math.isinf(fd) or math.isinf(sf):
        return 0.0 if fd == sf else math.inf
    sp = math.ulp(sf) if sf != 0.0 else math.ulp(0.0)
    with mpmath.workdps(SHADOW_DPS):
        return float(abs(mpmath.mpf(fd) - mpmath.mpf(s)) / sp)


# --------------------------------------------------------------------------- source helpers
def _innermost_stmt(tree, lineno):
    best = None
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and node.lineno <= lineno <= (node.end_lineno or node.lineno):
            span = (node.end_lineno or node.lineno) - node.lineno
            if best is None or span <= best[0]:
                best = (span, node)
    return best[1] if best else None


def _roots(stmt):
    if isinstance(stmt, (ast.If, ast.While)):
        return [stmt.test]
    if isinstance(stmt, ast.For):
        return [stmt.iter]
    if isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
        node = ast.BinOp(left=ast.Name(id=stmt.target.id, ctx=ast.Load()), op=stmt.op, right=stmt.value)
        return [ast.fix_missing_locations(ast.copy_location(node, stmt))]
    if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.Return, ast.Expr)) and stmt.value is not None:
        return [stmt.value]
    return []


def _children(node):
    if isinstance(node, ast.BinOp):
        return [node.left, node.right]
    if isinstance(node, ast.UnaryOp):
        return [node.operand]
    if isinstance(node, ast.Call):
        return list(node.args)
    return []


_OPS = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.Pow: "**"}


def _subexpr_table(stmt, d_mod, s_mod, d_locals, s_locals):
    """Evaluate every numeric sub-expression of a statement in both modes."""
    rows, by_id = [], {}
    for root in _roots(stmt):
        for node in ast.walk(root):
            if not isinstance(node, ast.expr) or isinstance(node, (ast.Lambda, ast.ListComp,
                                                                     ast.GeneratorExp, ast.DictComp, ast.SetComp)):
                continue
            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                    by_id[id(node)] = (node.value, node.value, 0.0)
                continue
            code = compile(ast.fix_missing_locations(ast.Expression(body=node)), "<autopsy>", "eval")
            try:
                dv = eval(code, vars(d_mod), dict(d_locals))
                with mpmath.workdps(SHADOW_DPS):
                    sv = eval(code, vars(s_mod), dict(s_locals))
            except Exception:
                continue
            if isinstance(dv, bool) or not isinstance(dv, (int, float)) or not (
                    isinstance(sv, (int, float, mpmath.mpf)) and not isinstance(sv, bool)):
                continue
            err = 0.0 if isinstance(dv, int) and isinstance(sv, int) else ulp_diff(dv, sv)
            by_id[id(node)] = (dv, sv, err)
            rows.append({"node": node, "expr": ast.unparse(node), "double": dv, "shadow": sv, "ulp": err})
    rows.sort(key=lambda r: len(r["expr"]))
    # the operation where digits are lost: bad itself, all numeric operands good
    for r in rows:
        node = r["node"]
        kids = [by_id[id(c)] for c in _children(node) if id(c) in by_id]
        r["lost_here"] = (r["ulp"] > BAD_ULP and bool(kids) and all(k[2] <= BAD_ULP for k in kids))
        r["note"] = ""
        if r["lost_here"] and isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
            with mpmath.workdps(SHADOW_DPS):
                big = max(abs(mpmath.mpf(kids[0][1])), abs(mpmath.mpf(kids[1][1])))
                ratio = abs(mpmath.mpf(r["shadow"])) / big if big else mpmath.mpf(1)
            if ratio < mpmath.mpf(2) ** -4:
                r["note"] = (f"cancellation: the result is {float(ratio):.1e} times the size of its "
                             f"operands, so the operands' rounding error is magnified")
        if r["lost_here"] and isinstance(node, ast.Call):
            r["note"] = "this call returns a bad value from good arguments"
    return rows


# --------------------------------------------------------------------------- the autopsy
def _frames(events_d, events_s):
    """Align the two traces; group aligned events by frame. Returns (frames, divergence)."""
    frames, divergence = {}, None
    for i, (ed, es) in enumerate(zip(events_d, events_s)):
        if ed[:4] != es[:4]:
            divergence = {"index": i, "double": ed[1:4], "shadow": es[1:4]}
            break
        frames.setdefault(ed[0], []).append((i, ed, es))
    else:
        if len(events_d) != len(events_s):
            divergence = {"index": min(len(events_d), len(events_s)), "double": "trace length",
                          "shadow": "trace length"}
    return frames, divergence


def _deaths(frame_events):
    """Lines in one frame after which some real-valued local goes from good to bad."""
    out = []
    for (i0, d0, s0), (i1, d1, s1) in zip(frame_events, frame_events[1:]):
        names = [n for n, v in d1[4].items() if _is_real(v)]
        changed = []
        for n in names:
            before = d0[4].get(n)
            if before is not None and before is d1[4][n]:
                continue
            after = ulp_diff(d1[4][n], s1[4].get(n, mpmath.nan))
            prev = ulp_diff(before, s0[4].get(n, mpmath.nan)) if _is_real(before) else None
            changed.append((n, prev, after, d1[4][n], s1[4].get(n)))
        if d1[3] == "return" and _is_real(d1[5]):
            changed.append(("<return value>", None, ulp_diff(d1[5], s1[5]), d1[5], s1[5]))
        for n, prev, after, dv, sv in changed:
            if after > BAD_ULP and (prev is None or prev <= BAD_ULP):
                out.append({"line": d0[2], "func": d0[1], "var": n, "before": prev, "after": after,
                            "double": dv, "shadow": sv, "ev_before": (i0, d0, s0), "ev_after": i1})
    return out


def autopsy(name: str, x: float, port_path: Path | None = None, reference=None) -> dict:
    path = Path(port_path or (REPO_ROOT / "routines" / f"{name}.py"))
    d_mod, s_mod = _load(path, name, False), _load(path, name, True)
    d_fn, s_fn = getattr(d_mod, name), getattr(s_mod, name)
    with mpmath.workdps(SHADOW_DPS):
        xs = mpmath.mpf(x)
        for f, a in ((d_fn, x), (s_fn, xs)):       # warm caches (first-call SAVE state) untraced
            try:
                f(a)
            except Exception:
                pass
        ev_d, calls_d, res_d = _trace(d_fn, x, str(path))
        ev_s, calls_s, res_s = _trace(s_fn, xs, str(path))
    tree = ast.parse(path.read_text(encoding="utf-8"))
    frames, divergence = _frames(ev_d, ev_s)

    out = {"name": name, "x": x, "double": res_d, "shadow": res_s,
           "result_ulp": ulp_diff(res_d, res_s) if not isinstance(res_d, Exception) else math.inf,
           "divergence": divergence, "chain": []}
    if reference is not None and not isinstance(res_s, Exception):
        with mpmath.workdps(SHADOW_DPS):
            out["shadow_vs_reference_ulp"] = ulp_diff(float(res_s), reference(mpmath.mpf(x)))

    k, depth = 0, 0
    while k in frames and depth < MAX_DEPTH:
        deaths = _deaths(frames[k])
        if not deaths:
            break
        dth = deaths[0]
        i0, d0, s0 = dth["ev_before"]
        stmt = _innermost_stmt(tree, dth["line"])
        rows = _subexpr_table(stmt, d_mod, s_mod, d0[4], s0[4]) if stmt is not None else []
        ints = {n: v for n, v in d0[4].items()
                if isinstance(v, int) and not isinstance(v, bool)
                and stmt is not None and n in {m.id for m in ast.walk(stmt) if isinstance(m, ast.Name)}}
        src = ast.unparse(stmt).splitlines()[0] if stmt is not None else "?"
        out["chain"].append({"func": dth["func"], "line": dth["line"], "source": src, "var": dth["var"],
                             "before_ulp": dth["before"], "after_ulp": dth["after"], "int_state": ints,
                             "subexpressions": [{k2: v for k2, v in r.items() if k2 != "node"} for r in rows],
                             "other_bad_lines": sorted({(d["func"], d["line"]) for d in deaths[1:]})[:5]})
        # drill into a helper call that returned a bad value from good arguments on that line
        lost_call = next((r for r in rows if r["lost_here"] and isinstance(r["node"], ast.Call)), None)
        if lost_call is None:
            break
        child = [c for c, (p, at) in calls_d.items() if p == k and i0 < at <= dth["ev_after"]]
        nxt = None
        for c in child:
            fe = frames.get(c)
            if fe and fe[-1][1][3] == "return" and ulp_diff(fe[-1][1][5], fe[-1][2][5]) > BAD_ULP:
                nxt = c
                break
        if nxt is None:
            break
        k, depth = nxt, depth + 1
    return out


def _fmt(v) -> str:
    if isinstance(v, mpmath.mpf):
        return mpmath.nstr(v, 17)
    if isinstance(v, float):
        return repr(v)
    return str(v)


def format_report(a: dict) -> str:
    lines = [f"Precision autopsy for {a['name']}({a['x']!r})",
             "  (the same code run twice: IEEE double vs 60-digit arithmetic; this measures rounding "
             "error only and suggests no fix)",
             f"  result: double {_fmt(a['double'])}   60-digit run {_fmt(a['shadow'])}   "
             f"difference {a['result_ulp']:.3g} ULP"]
    if "shadow_vs_reference_ulp" in a:
        lines.append(f"  60-digit run vs the 50-digit reference: {a['shadow_vs_reference_ulp']:.3g} ULP")
    if a["divergence"]:
        dv = a["divergence"]
        lines.append(f"  NOTE: control flow differs between the two runs at {dv['double']} vs {dv['shadow']}")
    if not a["chain"]:
        lines.append(f"  No line found where a value drifts more than {BAD_ULP:g} ULP from its 60-digit shadow.")
    for depth, c in enumerate(a["chain"]):
        ind = "  " * (depth + 1)
        state = (" with " + ", ".join(f"{n}={v}" for n, v in c["int_state"].items())) if c["int_state"] else ""
        before = "new" if c["before_ulp"] is None else f"{c['before_ulp']:.3g} ULP"
        lines.append(f"{ind}First line where a value goes bad: {c['func']}() line {c['line']}{state}")
        lines.append(f"{ind}  `{c['source']}`")
        lines.append(f"{ind}  {c['var']}: {before} before this line -> {c['after_ulp']:.3g} ULP after")
        if c["subexpressions"]:
            lines.append(f"{ind}  sub-expression values on entry to that line:")
            w = max(len(r["expr"]) for r in c["subexpressions"])
            for r in c["subexpressions"]:
                mark = "   <-- digits lost here" if r["lost_here"] else ""
                lines.append(f"{ind}    {r['expr']:<{w}}  double {_fmt(r['double']):<24} "
                             f"60-digit {_fmt(r['shadow']):<24} {r['ulp']:>9.3g} ULP{mark}")
                if r["note"]:
                    lines.append(f"{ind}    {'':<{w}}  ({r['note']})")
        if c["other_bad_lines"]:
            lines.append(f"{ind}  later lines that also go bad: " +
                         ", ".join(f"{f}() line {n}" for f, n in c["other_bad_lines"]))
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2:
        print(__doc__)
        return 2
    name = argv[0]
    ref = None
    try:
        from oracle.referees import get_referee
        ref = get_referee(name)["mpfn"]
    except Exception:
        pass
    for xs in argv[1:]:
        sys.stdout.write(format_report(autopsy(name, float(xs), reference=ref)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
