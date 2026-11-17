"""
harness/transcription.py - did the port copy the Fortran's constants correctly?

Every numeric DATA constant in fortran/slatec/<name>.f is compared with the module-level constant
of the same name in routines/<name>.py (NAME, name, _NAME or _name; arrays index from 1 in Fortran,
0 in Python). The port is read with ast, never imported. Only mismatches are reported; a renamed or
computed constant is counted as "not found" and not judged.

Why it exists: in the DCOT cold test (loop run 20261117T191654Z) the blind port mistyped two
Chebyshev coefficients. The trial saw failures, the autopsy saw a "logic" error (the 60-digit run
was wrong too), and four repair rounds changed correct code. A wrong constant is a copying error,
not a bug in the routine, and this check names it directly. It reports only what the port's own
source and the original's source say; it carries no information about how to fix the original.

  python -m harness.transcription <name>
"""

import ast
import math
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ULP_TOL = 2.0


def _statements(src: str) -> list[str]:
    """Fixed-form Fortran -> logical statements (continuation lines joined, comments dropped)."""
    out = []
    for line in src.splitlines():
        if not line.strip() or line[:1] in "Cc*!":
            continue
        body = line[6:72] if len(line) > 6 else ""
        if len(line) > 5 and line[5] not in " 0" and out:
            out[-1] += " " + body.strip()
        else:
            out.append(line[:72].strip())
    return out


def _fortran_number(text: str):
    t = text.replace(" ", "").upper().replace("D", "E")
    if not re.fullmatch(r"[+-]?(\d+\.?\d*|\.\d+)(E[+-]?\d+)?", t):
        return None
    return float(t)


def fortran_data(src: str) -> dict:
    """{(NAME, index or None): (value, source text)} for numeric DATA constants."""
    found = {}
    for st in _statements(src):
        if not re.match(r"DATA\b", st, re.I):
            continue
        for names, values in re.findall(r"([\w\s,()]+?)\s*/([^/]*)/", st[4:]):
            nl = [n.strip() for n in re.split(r",(?![^(]*\))", names) if n.strip()]
            vl = [v.strip() for v in values.split(",")]
            if len(nl) != len(vl):
                continue
            for n, v in zip(nl, vl):
                m = re.fullmatch(r"(\w+)\s*(?:\(\s*(\d+)\s*\))?", n)
                num = _fortran_number(v)
                if m and num is not None:
                    found[(m.group(1).upper(), int(m.group(2)) if m.group(2) else None)] = (num, v)
    return found


def python_constants(src: str) -> dict:
    """Module-level NAME = literal / [literals] assignments in the port."""
    out = {}
    for node in ast.parse(src).body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Name):
                    try:
                        out[t.id] = ast.literal_eval(node.value)
                    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
                        pass
    return out


def _lookup(consts: dict, name: str, idx):
    for cand in (name, name.lower(), "_" + name, "_" + name.lower()):
        if cand in consts:
            v = consts[cand]
            if idx is None:
                return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None
            if isinstance(v, (list, tuple)) and 0 < idx <= len(v):
                return v[idx - 1] if isinstance(v[idx - 1], (int, float)) else None
            return None
    return None


def check(name: str, fortran_src: str | None = None, port_src: str | None = None) -> dict:
    if fortran_src is None:
        fortran_src = (REPO_ROOT / "fortran" / "slatec" / f"{name}.f").read_text(encoding="utf-8", errors="replace")
    if port_src is None:
        port_src = (REPO_ROOT / "routines" / f"{name}.py").read_text(encoding="utf-8")
    data = fortran_data(fortran_src)
    try:
        consts = python_constants(port_src)
    except SyntaxError as exc:
        return {"compared": 0, "mismatches": [], "not_found": len(data), "error": f"port does not parse: {exc}"}
    mism, compared, missing = [], 0, 0
    for (fname, idx), (fv, text) in sorted(data.items(), key=lambda kv: (kv[0][0], kv[0][1] or 0)):
        pv = _lookup(consts, fname, idx)
        if pv is None:
            missing += 1
            continue
        compared += 1
        scale = math.ulp(fv) if fv != 0 else math.ulp(0.0)
        ulps = abs(float(pv) - fv) / scale
        if ulps > ULP_TOL:
            mism.append({"name": fname + (f"({idx})" if idx else ""), "fortran_text": text,
                         "fortran_value": fv, "port_value": float(pv), "ulps": ulps})
    return {"compared": compared, "mismatches": mism, "not_found": missing}


def format_report(name: str, res: dict) -> str:
    if res.get("error"):
        return f"Transcription check of routines/{name}.py: {res['error']}\n"
    if not res["mismatches"]:
        return ""
    lines = [f"{len(res['mismatches'])} of {res['compared']} DATA constants in fortran/slatec/{name}.f "
             f"differ from the same-named constant in routines/{name}.py:"]
    for m in res["mismatches"]:
        lines.append(f"  {m['name']:<12} Fortran DATA: {m['fortran_text']}")
        lines.append(f"  {'':<12} = {m['fortran_value']!r}   your port: {m['port_value']!r}   "
                     f"({m['ulps']:.3g} ULP apart)")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 1:
        print("usage: python -m harness.transcription <name>")
        return 2
    res = check(argv[0])
    print(format_report(argv[0], res) or f"All {res['compared']} DATA constants match "
          f"({res['not_found']} not found by name).")
    return 1 if res["mismatches"] else 0


if __name__ == "__main__":
    sys.exit(main())
