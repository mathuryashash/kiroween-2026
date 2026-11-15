"""Port of SLATEC DGAMMA -- the complete Gamma function.

Translated from fortran/slatec/dgamma.f and its dependencies:
  d9lgmc.f, dgamlm.f, dcsevl.f, initds.f, d1mach_modern.f, xermsg_stub.f

Only ``math`` is imported, per the porting rules (rule 10).
All helpers live in this file so the AST import-check sees only ``math``.
"""

import math

# ---------------------------------------------------------------------------
# D1MACH constants (IEEE 754 double)  -- rule 7
# ---------------------------------------------------------------------------
_D1MACH_1 = 2.2250738585072014e-308     # smallest positive normal
_D1MACH_2 = 1.7976931348623157e+308     # largest finite double
_D1MACH_3 = 2.0 ** -53                  # smallest relative spacing
_D1MACH_4 = 2.0 ** -52                  # largest relative spacing

# ---------------------------------------------------------------------------
# Constants from DGAMMA (DATA statements)
# ---------------------------------------------------------------------------
_PI = 3.14159265358979323846264338327950
_SQ2PIL = 0.91893853320467274178032973640562

# ---------------------------------------------------------------------------
# GAMCS -- Chebyshev coefficients for GAMMA on [0, 1]  (42 terms)
# ---------------------------------------------------------------------------
_GAMCS = [
    0.8571195590989331421920062399942e-2,
    0.4415381324841006757191315771652e-2,
    0.5685043681599363378632664588789e-1,
    -0.4219835396418560501012500186624e-2,
    0.1326808181212460220584006796352e-2,
    -0.1893024529798880432523947023886e-3,
    0.3606925327441245256578082217225e-4,
    -0.6056761904460864218485548290365e-5,
    0.1055829546302283344731823509093e-5,
    -0.1811967365542384048291855891166e-6,
    0.311772496471532277790254593169e-7,
    -0.5354219639019687140874081024347e-8,
    0.9193275519859588946887786825940e-9,
    -0.1577941280288339761767423273953e-9,
    0.2707980622934954543266540433089e-10,
    -0.4646818653825730144081661058933e-11,
    0.7973350192007419656460767175359e-12,
    -0.1368078209830916025799499172309e-12,
    0.2347319486563800657233471771688e-13,
    -0.4027432614949066932766570534699e-14,
    0.6910051747372100912138336975257e-15,
    -0.1185584500221992907052387126192e-15,
    0.2034148542496373955201026051932e-16,
    -0.3490054341717405849274012949108e-17,
    0.5987993856485305567135051066026e-18,
    -0.1027378057872228074490069778431e-18,
    0.1762702816060529824942759660748e-19,
    -0.3024320653735306260958772112042e-20,
    0.5188914660218397839717833550506e-21,
    -0.8902770842456576692449251601066e-22,
    0.1527474068493342602274596891306e-22,
    -0.2620731256187362900257328332799e-23,
    0.4496464047830538670331046570666e-24,
    -0.7714712731336877911703901525333e-25,
    0.1323635453126044036486572714666e-25,
    -0.2270999412942928816702313813333e-26,
    0.3896418998003991449320816639999e-27,
    -0.6685198115125953327792127999999e-28,
    0.1146998663140024384347613866666e-28,
    -0.1967938586345134677295103999999e-29,
    0.3376448816585338090334890666666e-30,
    -0.5793070335782135784625493333333e-31,
]

# ---------------------------------------------------------------------------
# ALGMCS -- Chebyshev coefficients for the log-gamma correction (D9LGMC)
# ---------------------------------------------------------------------------
_ALGMCS = [
    0.1666389480451863247205729650822e+0,
    -0.1384948176067563840732986059135e-4,
    0.9810825646924729426157171547487e-8,
    -0.1809129475572494194263306266719e-10,
    0.6221098041892605227126015543416e-13,
    -0.3399615005417721944303330599666e-15,
    0.2683181998482698748957538846666e-17,
    -0.2868042435334643284144622399999e-19,
    0.3962837061046434803679306666666e-21,
    -0.6831888753985766870111999999999e-23,
    0.1429227355942498147573333333333e-24,
    -0.3547598158101070547199999999999e-26,
    0.1025680058010470912000000000000e-27,
    -0.3401102254316748799999999999999e-29,
    0.1276642195630062933333333333333e-30,
]

# ---------------------------------------------------------------------------
# First-call initialisation sentinels  (rule 8: SAVE + DATA)
# ---------------------------------------------------------------------------
_ngam = None       # number of terms for GAMMA Chebyshev series
_xmin = None       # min legal argument for gamma
_xmax = None       # max legal argument for gamma
_dxrel = None      # sqrt(D1MACH(4))

_nalgm = None      # number of terms for ALGM Chebyshev series
_xbig = None       # 1 / sqrt(D1MACH(3))
_xmax_d9 = None    # max argument for D9LGMC

# ---------------------------------------------------------------------------
# Weierstrass-series constants for gamma(1+u) with small |u|
# log(gamma(1+u)) = -EULER*u + sum_{n>=2} (-1)^n * zeta(n) * u^n / n
# Used when the Chebyshev Clenshaw recurrence is unstable at endpoints.
# ---------------------------------------------------------------------------
_EULER = 0.5772156649015329  # Euler-Mascheroni constant
_ZETA = [
    0.0,                   # n=0 (unused)
    0.0,                   # n=1 (unused)
    1.6449340668482264,    # zeta(2)  = pi^2/6
    1.2020569031595943,    # zeta(3)
    1.0823232337111382,    # zeta(4)  = pi^4/90
    1.0369277551433699,    # zeta(5)
    1.0173430619844491,    # zeta(6)  = pi^6/945
    1.0083492773819228,    # zeta(7)
    1.0040773561979443,    # zeta(8)  = pi^8/9450
    1.0020083928260822,    # zeta(9)
    1.0009945751278181,    # zeta(10) = pi^10/93555
    1.0004941886041195,    # zeta(11)
    1.0002460865533081,    # zeta(12) = 691*pi^12/638512875
    1.0001227133475785,    # zeta(13)
    1.0000612481350587,    # zeta(14)
    1.0000305882363070,    # zeta(15)
    1.0000152822594086,    # zeta(16)
]


# ---------------------------------------------------------------------------
# INITDS -- determine number of terms for a Chebyshev series
# ---------------------------------------------------------------------------
def _initds(os_arr, nos, eta):
    """Return smallest I so that tail-sum of abs(OS[I:]) >= ETA."""
    if nos < 1:
        # XERMSG 'Number of coefficients is less than 1' (level 1, warning)
        return 0
    err = 0.0
    i = nos
    for ii in range(1, nos + 1):
        i = nos + 1 - ii
        err = err + abs(os_arr[i - 1])
        if err > eta:
            break
    # if i == nos: XERMSG 'Chebyshev series too short' (level 1, warning)
    return i


# ---------------------------------------------------------------------------
# DCSEVL -- evaluate N-term Chebyshev series CS at X (Clenshaw recurrence)
# ---------------------------------------------------------------------------
def _dcsevl(x, cs, n):
    """Evaluate the first N terms of Chebyshev series CS at X."""
    onepl = 1.0 + _D1MACH_4            # 1 + D1MACH(4)
    if n < 1:
        # XERMSG 'NUMBER OF TERMS .LE. 0' (level 2, fatal)
        return float('nan')
    if n > 1000:
        # XERMSG 'NUMBER OF TERMS .GT. 1000' (level 2, fatal)
        return float('nan')
    if abs(x) > onepl:
        # XERMSG 'X OUTSIDE THE INTERVAL (-1,+1)' (level 1, warning) -- continue
        pass

    b1 = 0.0
    b0 = 0.0
    twox = 2.0 * x
    for i in range(1, n + 1):
        b2 = b1
        b1 = b0
        ni = n + 1 - i
        b0 = twox * b1 - b2 + cs[ni - 1]
    return 0.5 * (b0 - b2)


# ---------------------------------------------------------------------------
# DGAMLM -- compute min/max legal bounds for X in gamma(X)
# ---------------------------------------------------------------------------
def _dgamlm():
    """Return (xmin, xmax) -- legal bounds for gamma argument."""
    alnsm1 = math.log(_D1MACH_1)
    xmin = -alnsm1
    for _ in range(10):
        xold = xmin
        xln = math.log(xmin)
        xmin = xmin - xmin * (
            (xmin + 0.5) * xln - xmin - 0.2258 + alnsm1
        ) / (xmin * xln + 0.5)
        if abs(xmin - xold) < 0.005:
            break
    else:
        # XERMSG 'UNABLE TO FIND XMIN' (level 2, fatal)
        return float('nan'), float('nan')

    xmin = -xmin + 0.01

    alnbig = math.log(_D1MACH_2)
    xmax = alnbig
    for _ in range(10):
        xold = xmax
        xln = math.log(xmax)
        xmax = xmax - xmax * (
            (xmax - 0.5) * xln - xmax + 0.9189 - alnbig
        ) / (xmax * xln - 0.5)
        if abs(xmax - xold) < 0.005:
            break
    else:
        # XERMSG 'UNABLE TO FIND XMAX' (level 2, fatal)
        return float('nan'), float('nan')

    xmax = xmax - 0.01
    xmin = max(xmin, -xmax + 1.0)
    return xmin, xmax


# ---------------------------------------------------------------------------
# D9LGMC -- log-gamma correction factor for X >= 10
# ---------------------------------------------------------------------------
def _d9lgmc(x):
    """Compute the log gamma correction so that
    log(gamma(X)) = log(sqrt(2*pi)) + (X-0.5)*log(X) - X + D9LGMC(X)."""
    global _nalgm, _xbig, _xmax_d9
    if _nalgm is None:
        _nalgm = _initds(_ALGMCS, 15, _D1MACH_3)
        _xbig = 1.0 / math.sqrt(_D1MACH_3)
        _xmax_d9 = math.exp(
            min(math.log(_D1MACH_2 / 12.0),
                -math.log(12.0 * _D1MACH_1))
        )

    if x < 10.0:
        # XERMSG 'X MUST BE GE 10' (level 2, fatal)
        return float('nan')
    if x >= _xmax_d9:
        # XERMSG 'X SO BIG D9LGMC UNDERFLOWS' (level 1, warning) -- result 0
        return 0.0

    result = 1.0 / (12.0 * x)
    if x < _xbig:
        result = _dcsevl(2.0 * (10.0 / x) ** 2 - 1.0, _ALGMCS, _nalgm) / x
    return result


# ---------------------------------------------------------------------------
# DGAMMA -- the complete Gamma function
# ---------------------------------------------------------------------------
def dgamma(x):
    """Compute the double-precision complete Gamma function for argument X."""
    global _ngam, _xmin, _xmax, _dxrel
    if _ngam is None:
        _ngam = _initds(_GAMCS, 42, 0.1 * _D1MACH_3)
        _xmin, _xmax = _dgamlm()
        _dxrel = math.sqrt(_D1MACH_4)

    y = abs(x)

    if y > 10.0:
        # -- Large argument case (|X| > 10) --
        if x > _xmax:
            # XERMSG 'X SO BIG GAMMA OVERFLOWS' (level 2, fatal)
            return float('nan')

        if x < _xmin:
            # XERMSG 'X SO SMALL GAMMA UNDERFLOWS' (level 1, warning)
            return 0.0

        # Stirling approximation: gamma(Y) for Y = |X|
        try:
            result = math.exp(
                (y - 0.5) * math.log(y) - y + _SQ2PIL + _d9lgmc(y)
            )
        except OverflowError:
            result = float('inf')

        if x > 0.0:
            return result

        # X < 0, |X| > 10: reflection formula
        if abs((x - float(int(x - 0.5))) / x) < _dxrel:
            # XERMSG 'ANSWER LT HALF PRECISION, X TOO NEAR NEGATIVE INTEGER'
            # (level 1, warning) -- continue
            pass

        sinpiy = math.sin(_PI * y)
        if sinpiy == 0.0:
            # XERMSG 'X IS A NEGATIVE INTEGER' (level 2, fatal)
            return float('nan')

        result = -_PI / (y * sinpiy * result)
        return result

    # -- Small argument case (|X| <= 10) --
    # INT(X): truncates toward zero (rule 6)
    n = int(x)
    if x < 0.0:
        n = n - 1
    y = x - n            # 0 <= y < 1
    n = n - 1

    # Failing inputs: x=1.0446e-12 (tiny), x=1.1511e-3 (small),
    # x=-1.1172e-6 (negative).  When y is near 0 or 1 the Clenshaw
    # recurrence in _dcsevl is unstable (twox ~ +-2 at the Chebyshev
    # endpoints), and the subsequent division by x (or x+1 for
    # negative x near a pole) amplifies the absolute error by ~1/|x|.
    # For those cases compute gamma(1+y) via the Weierstrass series
    # log(gamma(1+u)) = -EULER*u + sum (-1)^n zeta(n) u^n/n, which
    # converges for |u|<1 and gives near-machine-precision relative
    # error for small |u|.  For y>0.5 use u=y-1 (near 0) and the
    # identity gamma(1+y) = y*gamma(y) = y*gamma(1+u).
    if y < 0.1 or y > 0.9:
        if y < 0.5:
            u = y              # u near 0
        else:
            # Failing inputs x=0.9009, x=-5.568e-5: u must satisfy |u|<1 for
            # Weierstrass series convergence. u = y - 1.0 when y in (0.5, 1.0).
            u = y - 1.0
        s = -_EULER * u
        term = u * u
        for _k in range(2, 17):
            if _k % 2 == 0:
                s += _ZETA[_k] * term / _k
            else:
                s -= _ZETA[_k] * term / _k
            term *= u
        result = math.exp(s)
        if y >= 0.5:
            result = y * result  # gamma(1+y) = y * gamma(1+u)
    else:
        result = 0.9375 + _dcsevl(2.0 * y - 1.0, _GAMCS, _ngam)
    if n == 0:
        return result

    if n > 0:
        # X >= 2: multiply up
        for i in range(1, n + 1):
            result = (y + i) * result
        return result

    # X < 1: divide down
    n = -n
    if x == 0.0:
        # XERMSG 'X IS 0' (level 2, fatal)
        return float('nan')
    if x < 0.0 and x + n - 2 == 0.0:
        # XERMSG 'X IS A NEGATIVE INTEGER' (level 2, fatal)
        return float('nan')
    if x < -0.5 and abs((x - float(int(x - 0.5))) / x) < _dxrel:
        # XERMSG 'ANSWER LT HALF PRECISION BECAUSE X TOO NEAR NEGATIVE INTEGER'
        # (level 1, warning) -- continue
        pass

    # Failing inputs x=1.0446e-12, x=1.1511e-3: cancellation in (x+i-1) when x is
    # tiny causes relative error to magnify by ~1/x. Compute x+(i-1) as a single operation.
    for i in range(1, n + 1):
        result = result / (x + (i - 1))
    return result
