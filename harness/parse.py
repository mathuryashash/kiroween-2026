"""
harness/parse.py – strict float parser for Fortran ES25.17E3 output.

The tricky case: gfortran with a 3-digit exponent omits the 'E' marker,
so  5.39586561160790118-176  is a valid line meaning 5.395...e-176.
Anything else that is not a recognisable float raises ParseError with the
line number.

Gate requirement (from BUILD_CHUNKS.md / research/14 section B):
  parse_fortran_float("5.39586561160790118-176") -> ~5.4e-176  (no ValueError)
  parse_fortran_float("1.0E+300")               -> 1e300
  parse_fortran_float("garbage")                -> ParseError
"""

import re

class ParseError(ValueError):
    """Raised when a Fortran float line cannot be parsed."""

# Pattern: optional sign, digits, optional decimal, optional E/D exponent.
# Also handles the missing-E form:   1.23456-176  or  1.23456+002
_NORMAL  = re.compile(
    r'^\s*[+-]?\d+\.?\d*(?:[EeDd][+-]?\d+)?\s*$'
)
_MISSING_E = re.compile(
    r'^\s*([+-]?\d+\.?\d*)\s*([+-]\d+)\s*$'
)


def parse_fortran_float(line: str) -> float:
    """Parse one Fortran output line.  Raises ParseError on failure."""
    s = line.strip()
    if not s:
        raise ParseError(f"Empty line cannot be parsed as float")

    # Replace Fortran D-exponent with E for Python
    s_py = s.replace('D', 'E').replace('d', 'e')

    # Normal float (including E+300)
    try:
        return float(s_py)
    except ValueError:
        pass

    # Missing-E form: mantissa immediately followed by signed exponent
    m = _MISSING_E.match(s_py)
    if m:
        mantissa, exp = m.group(1), m.group(2)
        try:
            return float(f"{mantissa}E{exp}")
        except ValueError:
            pass

    raise ParseError(f"Cannot parse Fortran float: {line!r}")


def parse_fortran_lines(lines: list[str]) -> list[float]:
    """Parse a list of output lines.  Raises ParseError with line number on failure."""
    results = []
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if not s:
            continue
        try:
            results.append(parse_fortran_float(s))
        except ParseError as exc:
            raise ParseError(f"Line {i}: {exc}") from exc
    return results
