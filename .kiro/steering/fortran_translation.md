---
inclusion: always
---

# F77 → Python translation rules

Apply ALL of the following rules when porting SLATEC Fortran to Python.
Never use `scipy` or `mpmath` in a port — the harness must be able to call
the port without those libraries.  Use only `math` from the stdlib.

---

## 1. Implicit typing: I–N are integers
Fortran F77 implicit typing: variables whose names begin with I, J, K, L, M, N
are **integers** unless explicitly declared otherwise.  Check IMPLICIT and
REAL/DOUBLE PRECISION declarations in every routine before assuming a type.

## 2. 1-based loop bounds — translate literally
Fortran `DO I = 1, N` runs I = 1, 2, …, N inclusive.
Python equivalent: `for i in range(1, n + 1):` — do NOT convert to 0-based
unless you have a reason; mismatches in loop bounds silently change results.

## 3. DO loop trip count is computed once at entry
The trip count `MAX(0, INT((limit - start) / step) + 1)` is fixed before the
loop body executes.  Changing I inside the loop does not affect the count in
Fortran; replicate that with a precomputed range in Python when the bounds are
expressions.

## 4. GOTO → structured control flow
Replace arithmetic IF and GOTO with `if/elif/else` or `while`.  Label the
intent clearly in a comment.  Never replicate GOTO in Python.

## 5. Integer division truncates toward zero
`7 / 2 = 3` in Fortran (not 3.5, not 4).  Use Python `//` for integer
variables; watch out for mixed-type expressions where Fortran promotes to real.

## 6. DBLE / INT conversions — preserve evaluation order precisely
`DBLE(X)` → `float(x)` (widens to double).  `INT(X)` → `int(x)` (truncates
toward zero, like Fortran INT, NOT like Python `round`).

**Critical: preserve evaluation order exactly.**
Fortran evaluates `+`/`-` chains left to right, with mixed INTEGER/DOUBLE
operands converted at the point each operation happens. Python does the same for
floats, so translate expressions literally, keeping the original grouping.
Do not re-associate or "simplify" floating-point expressions on your own: any
deviation from the original must be driven by a failing trial and explained in
a comment that names the failing inputs.

## 7. D1MACH constants (IEEE double-precision)
Replace D1MACH calls with these literal IEEE-754 double constants (ports may
import only `math`, so do not use `sys.float_info`):

| D1MACH(N) | Meaning                     | Python                     |
|-----------|-----------------------------|----------------------------|
| D1MACH(1) | Smallest positive normal    | `2.2250738585072014e-308`  |
| D1MACH(2) | Largest finite double       | `1.7976931348623157e+308`  |
| D1MACH(3) | Smallest relative spacing   | `2.0 ** -53`               |
| D1MACH(4) | Largest relative spacing    | `2.0 ** -52`               |
| D1MACH(5) | log10(2)                    | `math.log10(2.0)`          |

## 8. SAVE + DATA — first-call initialisation
Fortran `DATA` with `SAVE` initialises a variable once and retains it across
calls.  Translate using a module-level variable with an `_initialised` flag, or
a function with `hasattr` on the function object:

```python
def csevl(x, cs, n):
    # (Chebyshev evaluation — no saved state needed here)
    ...
```

For routines that do initialise on first call (e.g. INITDS sets the order of a
Chebyshev series), mirror the logic with a module-level sentinel:

```python
_NCS = None   # filled on first call

def _init():
    global _NCS
    if _NCS is None:
        _NCS = initds(...)
```

## 9. Chebyshev series: CSEVL / INITDS semantics
`INITDS(OS, NOS, ETA)` returns the smallest N such that the tail sum of
`abs(OS[N:])` is less than `ETA`.  Translate literally; use the same loop.
`CSEVL(X, CS, N)` evaluates the first N terms of a Chebyshev expansion using
the Clenshaw recurrence.  Translate term-for-term; do not replace with
`numpy.polynomial.chebyshev` (different conventions).

## 10. Never call scipy or mpmath in a port
The port's only allowed import is `import math` (and `from math import ...`).
The harness AST-checks this before loading; violations → DISQUALIFIED verdict.
