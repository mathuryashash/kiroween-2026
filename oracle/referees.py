"""
oracle/referees.py – referee map: routine -> (mpmath_fn, domains).

Domains are named sub-domains with (lo, hi, n, sampling) triples.
Sampling: 'log' = log-uniform, 'lin' = linear-uniform.
Negative non-integer inputs avoid integers by >1e-6.

For dgamma the sub-domains are:
  tiny     : (1e-12, 1e-3)   log-uniform  – where the original bug bites hard
  small    : (1e-3, 1)       log-uniform
  mid      : (1, 30)         log-uniform
  large    : (30, 171)       log-uniform
  negative : (-30, 0)        log-uniform magnitudes, avoiding integers by 1e-5
"""

import math
import mpmath

mpmath.mp.dps = 50

# Map: scipy impl name -> scipy.special function
SCIPY_MAP: dict = {}

try:
    import scipy.special as _sp
    SCIPY_MAP["dgamma"] = _sp.gamma
    SCIPY_MAP["derfc"]  = _sp.erfc
    SCIPY_MAP["derf"]   = _sp.erf
except ImportError:
    pass


def _dgamma_domains() -> dict:
    return {
        "tiny":     {"lo": 1e-12, "hi": 1e-3,  "n_share": 0.15, "sampling": "log",      "sign": +1},
        "small":    {"lo": 1e-3,  "hi": 1.0,   "n_share": 0.20, "sampling": "log",      "sign": +1},
        "mid":      {"lo": 1.0,   "hi": 30.0,  "n_share": 0.30, "sampling": "log",      "sign": +1},
        "large":    {"lo": 30.0,  "hi": 171.0, "n_share": 0.20, "sampling": "log",      "sign": +1},
        "negative": {"lo": 1e-6,  "hi": 29.9,  "n_share": 0.15, "sampling": "log_neg",  "sign": -1},
    }


REFEREES: dict = {
    "dgamma": {
        "mpfn":    mpmath.gamma,
        "domains": _dgamma_domains(),
    },
}


def get_referee(name: str) -> dict:
    """Return {mpfn, domains} for a routine, or raise KeyError."""
    return REFEREES[name]


def make_inputs(name: str, n: int, seed: int) -> dict[str, list[float]]:
    """Generate seeded inputs for each sub-domain.  Returns {domain: [x, ...]}."""
    import random

    ref = get_referee(name)
    domains = ref["domains"]
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
            # Negative non-integer: magnitude log-uniform in [lo, hi]
            log_lo, log_hi = math.log(lo), math.log(hi)
            attempts = 0
            while len(xs) < count and attempts < count * 20:
                attempts += 1
                mag = math.exp(rng.uniform(log_lo, log_hi))
                x = -mag
                # avoid integers by > 1e-6
                if abs(x - round(x)) > 1e-6:
                    xs.append(x)
            # fill if needed
            while len(xs) < count:
                xs.append(-0.5 - rng.random() * 0.4)
        elif sampling == "lin":
            for _ in range(count):
                xs.append(rng.uniform(lo, hi))
        else:
            raise ValueError(f"Unknown sampling: {sampling}")

        result[dname] = xs

    return result
