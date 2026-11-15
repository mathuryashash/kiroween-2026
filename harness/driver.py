"""
harness/driver.py – generate, compile and run Fortran batch drivers.

spec step 2:
  - Generated Fortran 90 program for DOUBLE PRECISION f(x) signature
  - Reads N lines from stdin, writes ES25.17E3 (3-digit exponent, always has E)
  - COMMON flag set by xermsg stub causes that line to print NaN
  - Compile with -static -std=legacy -O0 -w -ffloat-store -fno-fast-math
  - Hard error if exit code != 0 or output line count != input count
"""

import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SLATEC_DIR = REPO_ROOT / "fortran" / "slatec"
SUPPORT_DIR = REPO_ROOT / "fortran" / "support"
VARIANTS_DIR = REPO_ROOT / "fortran" / "variants"
import os
import tempfile

# Build scratch lives outside the repo; override with GALVANI_WORK.
WORK_DIR = Path(os.environ.get("GALVANI_WORK") or (Path(tempfile.gettempdir()) / "galvani_build"))

COMPILE_FLAGS = [
    "-static",
    "-std=legacy",
    "-O0",
    "-w",
    "-ffloat-store",
    "-fno-fast-math",
]


def find_gfortran() -> str:
    """Resolve gfortran per spec priority: GALVANI_FC env, winlibs GCC16, MinGW 6.3."""
    env_fc = os.environ.get("GALVANI_FC")
    if env_fc:
        candidates = [env_fc]
    else:
        candidates = [
            "D:/tools/winlibs/mingw64/bin/gfortran.exe",
            "C:/MinGW/bin/gfortran.exe",
            "gfortran",
        ]
    for c in candidates:
        try:
            r = subprocess.run([c, "--version"], capture_output=True, timeout=10)
            if r.returncode == 0:
                return c
        except Exception:
            pass
    raise RuntimeError("No working gfortran found")


def gfortran_version(exe: str) -> str:
    r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10)
    return r.stdout.splitlines()[0].strip()


def _driver_source(routine: str) -> str:
    """Generate a Fortran 90 batch driver."""
    uname = routine.upper()
    return f"""\
! Auto-generated GALVANI batch driver for {uname}(x)
! Reads one double per stdin line, writes ES25.17E3 or NaN if xermsg fired.
      PROGRAM DRIVER_{uname}
      IMPLICIT NONE
      DOUBLE PRECISION X, RES
      DOUBLE PRECISION, EXTERNAL :: {uname}
      LOGICAL XERR_FLAG
      COMMON /XERMSG_FLAG/ XERR_FLAG
      INTEGER IOS
      DO
        XERR_FLAG = .FALSE.
        READ (*,*,IOSTAT=IOS) X
        IF (IOS .NE. 0) EXIT
        RES = {uname}(X)
        IF (XERR_FLAG) THEN
          WRITE (*,'(A)') 'NaN'
        ELSE
          WRITE (*,'(ES25.17E3)') RES
        END IF
      END DO
      END PROGRAM DRIVER_{uname}
"""


def _slatec_dep_files(routine: str) -> list[str]:
    """Return ordered list of .f files needed: support files + slatec deps.
    Uses what is already in fortran/slatec/ (fetch must have run first).
    """
    # Parse transitive deps via prologue (same logic as fetch, but only local)
    import re

    skip = {
        "d1mach", "i1mach", "r1mach",
        "xermsg", "xerror", "xercnt", "xerhlt", "xerprn",
        "xersve", "j4save", "fdump", "xgetua",
    }
    visited: set[str] = set()
    order: list[str] = []

    def collect(name: str):
        name = name.lower()
        if name in visited or name in skip:
            return
        visited.add(name)
        # Check variants dir first, then slatec
        for d in [VARIANTS_DIR, SLATEC_DIR]:
            p = d / f"{name}.f"
            if p.exists():
                # recurse into deps
                with open(p, encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        m = re.search(r"ROUTINES CALLED\s+(.*)", line, re.IGNORECASE)
                        if m:
                            for dep in re.split(r"[,\s]+", m.group(1)):
                                dep = dep.strip()
                                if dep and re.match(r'^[A-Z][A-Z0-9_]{0,30}$', dep, re.IGNORECASE):
                                    collect(dep.lower())
                if str(p) not in order:
                    order.append(str(p))
                return
        raise FileNotFoundError(f"Cannot find {name}.f in slatec or variants dirs")

    collect(routine)
    return order


def build_driver(
    routine: str,
    variant_f: str | None = None,
    work_dir: Path | None = None,
) -> tuple[str, str]:
    """Compile a driver exe.  Returns (exe_path, gfortran_version_line).

    variant_f: if set, use this .f file instead of fortran/slatec/<routine>.f
    """
    if work_dir is None:
        work_dir = WORK_DIR
    work_dir.mkdir(parents=True, exist_ok=True)

    gfortran = find_gfortran()
    fc_ver = gfortran_version(gfortran)

    # Determine the dep files
    dep_files = _slatec_dep_files(routine)

    # If a variant is requested, replace the last occurrence of the routine file
    if variant_f:
        routine_base = f"{routine.lower()}.f"
        dep_files = [
            f for f in dep_files
            if not (f.endswith(routine_base) and Path(f).parent == SLATEC_DIR)
        ]
        if str(variant_f) not in dep_files:
            dep_files.append(str(variant_f))

    # Support files
    support_files = [
        str(SUPPORT_DIR / "d1mach_modern.f"),
        str(SUPPORT_DIR / "xermsg_stub.f"),
    ]

    # Generate driver source
    suffix = "fixed" if variant_f else "orig"
    driver_src = work_dir / f"{routine}_{suffix}_driver.f90"
    driver_src.write_text(_driver_source(routine), encoding="utf-8")

    # Exe name must NOT contain patch/setup/install/update
    exe_path = str(work_dir / f"{routine}_{suffix}_drv.exe")

    cmd = (
        [gfortran]
        + COMPILE_FLAGS
        + support_files
        + dep_files
        + [str(driver_src), "-o", exe_path]
    )
    t0 = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    elapsed = time.perf_counter() - t0

    if r.returncode != 0:
        raise RuntimeError(
            f"Compilation failed in {elapsed:.1f}s:\n{r.stderr}"
        )
    return exe_path, fc_ver


def run_batch(exe: str, inputs: list[float]) -> tuple[list[float], float]:
    """Run driver exe on inputs, parse outputs.  Hard error on mismatch.

    Returns (results, elapsed_s).
    NaN lines (from xermsg flag) are kept as float('nan').
    """
    from harness.parse import parse_fortran_lines, ParseError

    inp_text = "\n".join(f"{x:.17e}" for x in inputs) + "\n"
    t0 = time.perf_counter()
    r = subprocess.run(
        [exe], input=inp_text, capture_output=True, text=True, timeout=120
    )
    elapsed = time.perf_counter() - t0

    if r.returncode != 0:
        raise RuntimeError(
            f"Driver exited with code {r.returncode}. stderr: {r.stderr[:500]}"
        )

    out_lines = [l for l in r.stdout.splitlines() if l.strip()]

    if len(out_lines) != len(inputs):
        raise RuntimeError(
            f"Output line count mismatch: expected {len(inputs)}, got {len(out_lines)}. "
            f"stderr: {r.stderr[:200]}"
        )

    # Parse: NaN lines pass through as float('nan')
    results = []
    for i, line in enumerate(out_lines, 1):
        s = line.strip()
        if s.upper() == "NAN":
            results.append(float("nan"))
        else:
            try:
                from harness.parse import parse_fortran_float
                results.append(parse_fortran_float(s))
            except Exception as exc:
                raise RuntimeError(f"Unparsable output line {i}: {line!r}") from exc

    return results, elapsed
