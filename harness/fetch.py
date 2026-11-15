"""
harness/fetch.py – fetch SLATEC FNLIB routine + transitive deps from netlib.

spec step 1:
  python -m harness.fetch <name>
  - Downloads <name>.f + all ROUTINES CALLED deps (recursive)
  - Skips d1mach / i1mach / r1mach / xermsg / xerror family (fortran/support/)
  - Records url + sha256 + date in fortran/slatec/SOURCES.md (idempotent)
  - Caches: won't re-download if file exists and sha256 matches

Usage:
  python -m harness.fetch dgamma
"""

import hashlib
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SLATEC_DIR = REPO_ROOT / "fortran" / "slatec"
SUPPORT_DIR = REPO_ROOT / "fortran" / "support"

FNLIB_BASE = "https://www.netlib.org/slatec/fnlib"
SRC_BASE   = "https://www.netlib.org/slatec/src"

# Routines we provide ourselves (skip fetching)
SKIP_ROUTINES = {
    "d1mach", "i1mach", "r1mach",
    "xermsg", "xerror", "xercnt", "xerhlt", "xerprn", "xersve",
    "j4save", "fdump", "xgetua", "xerabt", "xersav",
}


def _sha256(path: Path) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _fetch_url(name: str) -> tuple[bytes, str]:
    """Try fnlib then src; return (content, url_used).  Raises if not found."""
    for base in [FNLIB_BASE, SRC_BASE]:
        url = f"{base}/{name}.f"
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                return resp.read(), url
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                continue
            raise
    raise FileNotFoundError(f"Cannot find {name}.f on netlib (fnlib or src)")


def _parse_deps(path: Path) -> list[str]:
    """Extract ROUTINES CALLED names from prologue."""
    deps = []
    in_called = False
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            upper = line.upper()
            m = re.search(r"ROUTINES CALLED\s+(.*)", upper)
            if m:
                raw = m.group(1).strip()
                in_called = True
            elif in_called and upper.startswith("C***"):
                in_called = False
            else:
                raw = None
            if m or (in_called and not upper.startswith("C***")):
                chunk = m.group(1).strip() if m else line.strip().lstrip("C").strip()
                for name in re.split(r"[,\s]+", chunk):
                    name = name.strip()
                    if name and re.match(r'^[A-Z][A-Z0-9_]{0,30}$', name, re.IGNORECASE):
                        deps.append(name.lower())
    return deps


def ensure_routine(name: str, visited: set | None = None) -> list[str]:
    """Ensure <name>.f is in fortran/slatec/, fetching if needed.
    Returns list of file paths in dependency order."""
    if visited is None:
        visited = set()
    name = name.lower()
    if name in visited:
        return []
    visited.add(name)

    if name in SKIP_ROUTINES:
        return []

    dest = SLATEC_DIR / f"{name}.f"
    if not dest.exists():
        print(f"  fetch: {name}.f ...", end=" ", flush=True)
        content, url = _fetch_url(name)
        dest.write_bytes(content)
        print(f"ok ({len(content)} bytes)")
        # Record in SOURCES.md
        _record_source(dest, url)
    else:
        print(f"  cached: {name}.f")

    result = []
    for dep in _parse_deps(dest):
        result.extend(ensure_routine(dep, visited))
    if str(dest) not in result:
        result.append(str(dest))
    return result


def _sources_path() -> Path:
    return SLATEC_DIR / "SOURCES.md"


def _record_source(path: Path, url: str) -> None:
    """Add or update entry in SOURCES.md (idempotent by filename)."""
    fname = path.name
    digest = _sha256(path)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = f"| {fname} | {url} | `{digest}` | {date} |"

    sp = _sources_path()
    if sp.exists():
        lines = sp.read_text(encoding="utf-8").splitlines()
        # Update if already present
        for i, line in enumerate(lines):
            if line.startswith(f"| {fname} |"):
                lines[i] = row
                sp.write_text("\n".join(lines) + "\n", encoding="utf-8")
                return
        # Append
        sp.write_text(sp.read_text() + row + "\n", encoding="utf-8")
    else:
        header = "# SLATEC FNLIB sources\n\n| file | url | sha256 | fetched |\n|------|-----|--------|---------|"
        sp.write_text(header + "\n" + row + "\n", encoding="utf-8")


def fetch_all_deps(name: str) -> list[str]:
    """Public entry: fetch routine + deps. Returns ordered dep list."""
    SLATEC_DIR.mkdir(parents=True, exist_ok=True)
    return ensure_routine(name)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m harness.fetch <routine>")
        sys.exit(1)
    files = fetch_all_deps(sys.argv[1].lower())
    print(f"\nDependency files ({len(files)}):")
    for f in files:
        print(f"  {os.path.basename(f)}")
