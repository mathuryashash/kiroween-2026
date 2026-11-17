"""tests/test_transcription.py - the DATA-constant check, on toy sources (no files needed)."""
from harness.transcription import check, fortran_data, format_report

FORTRAN = """      DOUBLE PRECISION FUNCTION DTOY (X)
      DOUBLE PRECISION X, TOYCS(3), PIREC, A, B
      DATA TOYCS(  1) / +.2402591609 8295630250 9554617744 234 D+0    /
      DATA TOYCS(  2) / -.1653303160 1500227845 4746025255 758 D-1    /
      DATA TOYCS(  3) / -.4299839193 1724018935 6476228239 895 D-4    /
      DATA PIREC / .01161977236 7581343075 5350534900 57 D0 /
      DATA A, B / 1.5D0, 2.5D0 /
      DATA FIRST /.TRUE./
      DTOY = X
      RETURN
      END
"""

GOOD = """
TOYCS = [+.24025916098295630250e0, -.16533031601500227845e-1, -.42998391931724018935e-4]
PIREC = .011619772367581343075
_A = 1.5
b = 2.5
"""


def test_reads_blank_separated_fortran_numbers():
    d = fortran_data(FORTRAN)
    assert d[("TOYCS", 3)][0] == -.42998391931724018935e-4
    assert d[("PIREC", None)][0] == .011619772367581343075
    assert d[("A", None)][0] == 1.5 and d[("B", None)][0] == 2.5
    assert ("FIRST", None) not in d


def test_correct_port_has_no_findings():
    r = check("toy", FORTRAN, GOOD)
    assert r["compared"] == 6 and r["mismatches"] == [] and format_report("toy", r) == ""


def test_swapped_digits_are_named():
    bad = GOOD.replace("-.42998391931724018935e-4", "-.43099391917240189356e-4")
    r = check("toy", FORTRAN, bad)
    assert [m["name"] for m in r["mismatches"]] == ["TOYCS(3)"]
    assert "TOYCS(3)" in format_report("toy", r)


def test_renamed_or_computed_constants_are_not_judged():
    r = check("toy", FORTRAN, "PI_RECIPROCAL = 0.0116\nTOYCS = make()\n")
    assert r["compared"] == 0 and r["mismatches"] == [] and r["not_found"] == 6
