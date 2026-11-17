"""
oracle/referees.py - referee map: routine -> (mpmath function, input sub-domains).

The referee is mpmath at 50 digits. Each entry is the function the routine's SLATEC
prologue says it computes. Where SLATEC returns a real value for an input at which the
textbook function is complex (DE1 and DLNGAM for x < 0, DSPENC for x > 1), the
referee takes the real part, which is what the prologue defines.

Sub-domain spec keys:
  lo, hi     magnitude range
  n_share    share of the n inputs
  sampling   'log'     x log-uniform in [lo, hi]
             'log_neg' x = -m, m log-uniform in [lo, hi], avoiding integers by > 1e-6
             'near'    x = center + sign * d, d log-uniform in [lo, hi]
             'lin'     x uniform in [lo, hi]
"""

import math

import mpmath

mpmath.mp.dps = 50

# Living descendants: the same function in current SciPy, for the ledger's comparison column.
SCIPY_MAP: dict = {}
try:
    import scipy.special as _sp

    SCIPY_MAP.update({
        "dgamma": _sp.gamma, "derf": _sp.erf, "derfc": _sp.erfc, "ddaws": _sp.dawsn,
        "dbesi0": _sp.i0, "dbesi1": _sp.i1, "dbsi0e": _sp.i0e, "dbsi1e": _sp.i1e,
        "dbesj0": _sp.j0, "dbesj1": _sp.j1, "dbesy0": _sp.y0, "dbesy1": _sp.y1,
        "dbesk0": _sp.k0, "dbesk1": _sp.k1, "dbsk0e": _sp.k0e, "dbsk1e": _sp.k1e,
        "dai": lambda x: _sp.airy(x)[0], "dbi": lambda x: _sp.airy(x)[2],
        "dcbrt": _sp.cbrt, "dcosdg": _sp.cosdg, "dsindg": _sp.sindg,
        "de1": lambda x: _sp.exp1(x) if x > 0 else -_sp.expi(-x),
        "dei": _sp.expi, "dexprl": _sp.exprel, "dgamr": _sp.rgamma, "dlngam": _sp.gammaln,
        "dlnrel": _sp.log1p, "dpsi": _sp.psi,
        "dspenc": lambda x: _sp.spence(1.0 - x) if x <= 1.0 else float("nan"),
    })
except ImportError:
    pass


def _rcbrt(x):
    return mpmath.sign(x) * mpmath.cbrt(abs(x))


def _dawson(x):
    return mpmath.sqrt(mpmath.pi) / 2 * mpmath.exp(-x * x) * mpmath.erfi(x)


def _deg(f):
    return lambda x: f(x * mpmath.pi / 180)


def _aie(x):
    return mpmath.airyai(x) * mpmath.exp(mpmath.mpf(2) / 3 * x ** 1.5) if x > 0 else mpmath.airyai(x)


def _bie(x):
    return mpmath.airybi(x) * mpmath.exp(-mpmath.mpf(2) / 3 * x ** 1.5) if x > 0 else mpmath.airybi(x)


def D(lo, hi, share, sampling="log", center=None, sign=+1):
    d = {"lo": lo, "hi": hi, "n_share": share, "sampling": sampling, "sign": sign}
    if center is not None:
        d["center"] = center
    return d


NEG = "log_neg"

REFEREES: dict = {
    "dgamma": {"mpfn": mpmath.gamma, "domains": {
        "tiny": D(1e-12, 1e-3, 0.15), "small": D(1e-3, 1.0, 0.20), "mid": D(1.0, 30.0, 0.30),
        "large": D(30.0, 171.0, 0.20), "negative": D(1e-6, 29.9, 0.15, NEG, sign=-1)}},
    "derf": {"mpfn": mpmath.erf, "domains": {
        "tiny": D(1e-12, 1e-2, 0.2), "mid": D(1e-2, 6.0, 0.6), "negative": D(1e-6, 6.0, 0.2, NEG)}},
    "derfc": {"mpfn": mpmath.erfc, "domains": {
        "small": D(1e-6, 1.0, 0.2), "mid": D(1.0, 15.0, 0.4), "far_tail": D(15.0, 26.5, 0.2, "lin"),
        "negative": D(1e-6, 6.0, 0.2, NEG)}},
    "dasinh": {"mpfn": mpmath.asinh, "domains": {
        "tiny": D(1e-10, 1e-2, 0.25), "mid": D(1e-2, 10.0, 0.25), "large": D(10.0, 1e300, 0.25),
        "negative": D(1e-10, 1e10, 0.25, NEG)}},
    "dacosh": {"mpfn": mpmath.acosh, "domains": {
        "near_1": D(1e-12, 1e-2, 0.35, "near", center=1.0), "mid": D(1.01, 10.0, 0.35),
        "large": D(10.0, 1e300, 0.30)}},
    "datanh": {"mpfn": mpmath.atanh, "domains": {
        "tiny": D(1e-12, 1e-2, 0.25), "mid": D(1e-2, 0.9, 0.25),
        "near_1": D(1e-12, 1e-1, 0.25, "near", center=1.0, sign=-1),
        "negative": D(1e-12, 0.999, 0.25, NEG)}},
    "ddaws": {"mpfn": _dawson, "domains": {
        "tiny": D(1e-10, 1e-2, 0.25), "mid": D(1e-2, 10.0, 0.35), "large": D(10.0, 1e10, 0.2),
        "negative": D(1e-3, 100.0, 0.2, NEG)}},
    "dbesi0": {"mpfn": lambda x: mpmath.besseli(0, x), "domains": {
        "small": D(1e-10, 3.0, 0.4), "mid": D(3.0, 700.0, 0.4), "negative": D(1e-3, 50.0, 0.2, NEG)}},
    "dbesi1": {"mpfn": lambda x: mpmath.besseli(1, x), "domains": {
        "small": D(1e-10, 3.0, 0.4), "mid": D(3.0, 700.0, 0.4), "negative": D(1e-3, 50.0, 0.2, NEG)}},
    "dbsi0e": {"mpfn": lambda x: mpmath.exp(-abs(x)) * mpmath.besseli(0, x), "domains": {
        "small": D(1e-10, 3.0, 0.4), "mid": D(3.0, 1e8, 0.4), "negative": D(1e-3, 1e4, 0.2, NEG)}},
    "dbsi1e": {"mpfn": lambda x: mpmath.exp(-abs(x)) * mpmath.besseli(1, x), "domains": {
        "small": D(1e-10, 3.0, 0.4), "mid": D(3.0, 1e8, 0.4), "negative": D(1e-3, 1e4, 0.2, NEG)}},
    "dbesj0": {"mpfn": lambda x: mpmath.besselj(0, x), "domains": {
        "small": D(1e-10, 4.0, 0.3), "mid": D(4.0, 100.0, 0.4), "large": D(100.0, 1e6, 0.3)}},
    "dbesj1": {"mpfn": lambda x: mpmath.besselj(1, x), "domains": {
        "small": D(1e-10, 4.0, 0.3), "mid": D(4.0, 100.0, 0.4), "large": D(100.0, 1e6, 0.3)}},
    "dbesy0": {"mpfn": lambda x: mpmath.bessely(0, x), "domains": {
        "small": D(1e-10, 4.0, 0.3), "mid": D(4.0, 100.0, 0.4), "large": D(100.0, 1e6, 0.3)}},
    "dbesy1": {"mpfn": lambda x: mpmath.bessely(1, x), "domains": {
        "small": D(1e-10, 4.0, 0.3), "mid": D(4.0, 100.0, 0.4), "large": D(100.0, 1e6, 0.3)}},
    "dbesk0": {"mpfn": lambda x: mpmath.besselk(0, x), "domains": {
        "small": D(1e-10, 2.0, 0.5), "mid": D(2.0, 700.0, 0.5)}},
    "dbesk1": {"mpfn": lambda x: mpmath.besselk(1, x), "domains": {
        "small": D(1e-10, 2.0, 0.5), "mid": D(2.0, 700.0, 0.5)}},
    "dbsk0e": {"mpfn": lambda x: mpmath.exp(x) * mpmath.besselk(0, x), "domains": {
        "small": D(1e-10, 2.0, 0.5), "mid": D(2.0, 1e8, 0.5)}},
    "dbsk1e": {"mpfn": lambda x: mpmath.exp(x) * mpmath.besselk(1, x), "domains": {
        "small": D(1e-10, 2.0, 0.5), "mid": D(2.0, 1e8, 0.5)}},
    "dai": {"mpfn": mpmath.airyai, "domains": {
        "negative": D(1e-3, 100.0, 0.4, NEG), "small": D(1e-6, 2.0, 0.3), "mid": D(2.0, 80.0, 0.3)}},
    "dbi": {"mpfn": mpmath.airybi, "domains": {
        "negative": D(1e-3, 100.0, 0.4, NEG), "small": D(1e-6, 2.0, 0.3), "mid": D(2.0, 80.0, 0.3)}},
    "daie": {"mpfn": _aie, "domains": {
        "negative": D(1e-3, 100.0, 0.3, NEG), "small": D(1e-6, 2.0, 0.3), "mid": D(2.0, 1e6, 0.4)}},
    "dbie": {"mpfn": _bie, "domains": {
        "negative": D(1e-3, 100.0, 0.3, NEG), "small": D(1e-6, 2.0, 0.3), "mid": D(2.0, 1e6, 0.4)}},
    "dcbrt": {"mpfn": _rcbrt, "domains": {
        "positive": D(1e-300, 1e300, 0.5), "negative": D(1e-300, 1e300, 0.5, NEG)}},
    "dcosdg": {"mpfn": _deg(mpmath.cos), "domains": {
        "mid": D(1e-3, 360.0, 0.4), "large": D(360.0, 1e6, 0.3),
        "near_90": D(1e-10, 1.0, 0.3, "near", center=90.0)}},
    "dsindg": {"mpfn": _deg(mpmath.sin), "domains": {
        "mid": D(1e-3, 360.0, 0.4), "large": D(360.0, 1e6, 0.3),
        "near_180": D(1e-10, 1.0, 0.3, "near", center=180.0)}},
    "dcot": {"mpfn": mpmath.cot, "domains": {
        "small": D(1e-10, 1.0, 0.4), "mid": D(1.0, 1e3, 0.4),
        "near_pi": D(1e-10, 1e-2, 0.2, "near", center=math.pi)}},
    "de1": {"mpfn": lambda x: mpmath.re(mpmath.e1(x)), "domains": {
        "small": D(1e-10, 1.0, 0.3), "mid": D(1.0, 700.0, 0.4), "negative": D(1e-6, 700.0, 0.3, NEG)}},
    "dei": {"mpfn": mpmath.ei, "domains": {
        "small": D(1e-10, 1.0, 0.25), "mid": D(1.0, 700.0, 0.3),
        "near_root": D(1e-12, 1e-2, 0.15, "near", center=0.37250741078136663),
        "negative": D(1e-10, 700.0, 0.3, NEG)}},
    "dli": {"mpfn": mpmath.li, "domains": {
        "small": D(1e-10, 0.9, 0.3), "near_root": D(1e-12, 1e-2, 0.2, "near", center=1.4513692348833810),
        "mid": D(2.0, 1e300, 0.5)}},
    "dexprl": {"mpfn": lambda x: mpmath.expm1(x) / x, "domains": {
        "tiny": D(1e-12, 1e-2, 0.35), "mid": D(1e-2, 700.0, 0.35), "negative": D(1e-12, 700.0, 0.3, NEG)}},
    "dgamr": {"mpfn": mpmath.rgamma, "domains": {
        "small": D(1e-12, 1.0, 0.35), "mid": D(1.0, 170.0, 0.35), "negative": D(1e-6, 170.0, 0.3, NEG)}},
    "dlngam": {"mpfn": lambda x: mpmath.re(mpmath.loggamma(x)), "domains": {
        "tiny": D(1e-12, 1e-3, 0.15), "small": D(1e-3, 0.99, 0.15),
        "near_1": D(1e-10, 1e-2, 0.1, "near", center=1.0),
        "near_2": D(1e-10, 1e-2, 0.1, "near", center=2.0),
        "mid": D(2.01, 1e3, 0.15), "large": D(1e3, 1e300, 0.15), "negative": D(1e-6, 1e3, 0.2, NEG)}},
    "dlnrel": {"mpfn": mpmath.log1p, "domains": {
        "tiny": D(1e-12, 1e-2, 0.3), "mid": D(1e-2, 1e300, 0.3), "negative": D(1e-12, 0.5, 0.2, NEG),
        "near_m1": D(1e-12, 1e-2, 0.2, "near", center=-1.0)}},
    "dpsi": {"mpfn": mpmath.digamma, "domains": {
        "small": D(1e-10, 1.0, 0.2), "mid": D(1.0, 1e3, 0.2), "large": D(1e3, 1e300, 0.15),
        "near_root": D(1e-12, 1e-2, 0.15, "near", center=1.4616321449683623),
        "negative": D(1e-6, 1e3, 0.3, NEG)}},
    "dspenc": {"mpfn": lambda x: mpmath.re(mpmath.polylog(2, x)), "domains": {
        "negative": D(1e-10, 1e6, 0.3, NEG), "small": D(1e-10, 0.5, 0.25),
        "mid": D(0.5, 2.0, 0.2, "lin"), "large": D(2.0, 1e6, 0.25)}},
}

# Trialled by hand before the pipeline existed (spike, council rounds). They stay in the
# census as controls but are not eligible as cold-test candidates.
HAND_TOUCHED = {"dgamma", "derf", "derfc", "dbesk0", "dbesj0", "dbesy0", "dai"}


def get_referee(name: str) -> dict:
    """Return {mpfn, domains} for a routine, or raise KeyError."""
    return REFEREES[name]


def make_inputs(name: str, n: int, seed: int) -> dict[str, list[float]]:
    """Generate seeded inputs for each sub-domain. Returns {domain: [x, ...]}."""
    import random

    domains = get_referee(name)["domains"]
    rng = random.Random(seed)

    total_share = sum(d["n_share"] for d in domains.values())
    result = {}
    for dname, spec in domains.items():
        count = max(1, round(n * spec["n_share"] / total_share))
        lo, hi = spec["lo"], spec["hi"]
        sampling = spec["sampling"]

        xs = []
        if sampling == "log":
            log_lo, log_hi = math.log(lo), math.log(hi)
            for _ in range(count):
                xs.append(math.exp(rng.uniform(log_lo, log_hi)))
        elif sampling == "log_neg":
            log_lo, log_hi = math.log(lo), math.log(hi)
            attempts = 0
            while len(xs) < count and attempts < count * 20:
                attempts += 1
                x = -math.exp(rng.uniform(log_lo, log_hi))
                if abs(x - round(x)) > 1e-6:      # avoid integers (poles of gamma-type functions)
                    xs.append(x)
            while len(xs) < count:
                xs.append(-0.5 - rng.random() * 0.4)
        elif sampling == "near":
            c, s = spec["center"], spec.get("sign", +1)
            log_lo, log_hi = math.log(lo), math.log(hi)
            while len(xs) < count:
                x = c + s * math.exp(rng.uniform(log_lo, log_hi))
                if x != c:
                    xs.append(x)
        elif sampling == "lin":
            for _ in range(count):
                xs.append(rng.uniform(lo, hi))
        else:
            raise ValueError(f"Unknown sampling: {sampling}")

        result[dname] = xs

    return result
