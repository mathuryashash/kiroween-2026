"""
Port of SLATEC FNLIB DGAMR: reciprocal of the Gamma function.
Translates DGAMR and all dependencies (DGAMMA, DLGAMS, DLNGAM, DCSEVL, INITDS, DGAMLM, D9LGMC).
Imports only math; no scipy, numpy, or mpmath.
"""

import math


# =============================================================================
# D1MACH constants (IEEE-754 double precision)
# =============================================================================

def _d1mach(i):
    """IEEE double machine constants, indexed 1-5."""
    # Based on d1mach_modern.f via Fortran intrinsics
    if i == 1:
        return 2.2250738585072014e-308  # TINY (smallest positive normal)
    elif i == 2:
        return 1.7976931348623157e+308  # HUGE (largest finite double)
    elif i == 3:
        return 1.1102230246251565e-16   # EPSILON / 2 (D1MACH(3))
    elif i == 4:
        return 2.220446049250313e-16    # EPSILON (D1MACH(4))
    elif i == 5:
        return math.log10(2.0)          # LOG10(2)
    return 0.0


# =============================================================================
# INITDS: Determine number of terms needed in Chebyshev series
# =============================================================================

def _initds(os, nos, eta):
    """
    Determine the number of terms needed in an orthogonal polynomial series
    so that it meets specified accuracy ETA.
    Returns the smallest index I such that the tail sum is < ETA.
    Translates INITDS literally (line 1-based iteration).
    """
    err = 0.0
    for ii in range(1, nos + 1):
        i = nos + 1 - ii
        err = err + abs(os[i - 1])  # os is 0-indexed in Python
        if err > eta:
            return i
    return i


# =============================================================================
# DCSEVL: Evaluate a Chebyshev series
# =============================================================================

def _dcsevl(x, cs, n):
    """
    Evaluate the N-term Chebyshev series CS at X using Clenshaw recurrence.
    CS is 0-indexed in Python (passed as list/array).
    Returns 0.5*(B0 - B2) where B0, B1, B2 follow the recurrence.
    """
    b0 = 0.0
    b1 = 0.0
    twox = 2.0 * x
    for i in range(1, n + 1):
        b2 = b1
        b1 = b0
        ni = n + 1 - i
        b0 = twox * b1 - b2 + cs[ni - 1]  # cs is 0-indexed
    return 0.5 * (b0 - b2)


# =============================================================================
# D9LGMC: Log Gamma correction factor for X >= 10
# =============================================================================

_D9LGMC_INITIALIZED = False
_NALGM = None
_XBIG = None
_XMAX_LGMC = None

def _d9lgmc(x):
    """
    Compute the log Gamma correction factor for X >= 10:
    LOG(DGAMMA(X)) = LOG(SQRT(2*PI)) + (X-0.5)*LOG(X) - X + D9LGMC(X)
    """
    global _D9LGMC_INITIALIZED, _NALGM, _XBIG, _XMAX_LGMC
    
    # Chebyshev coefficients for ALGM series (15 terms)
    algmcs = [
        +.1666389480451863247,
        -.1384948176067563841e-4,
        +.9810825646924729443e-8,
        -.1809129475572494194e-10,
        +.6221098041892605227e-13,
        -.3399615005417721944e-15,
        +.2683181998482698749e-17,
        -.2868042435334643284e-19,
        +.3962837061046434804e-21,
        -.6831888753985766870e-23,
        +.1429227355942498148e-24,
        -.3547598158101070547e-26,
        +.1025680058010470912e-27,
        -.3401102254316748800e-29,
        +.1276642195630062933e-30
    ]
    
    if not _D9LGMC_INITIALIZED:
        _D9LGMC_INITIALIZED = True
        _NALGM = _initds(algmcs, 15, _d1mach(3))
        _XBIG = 1.0 / math.sqrt(_d1mach(3))
        _XMAX_LGMC = math.exp(min(math.log(_d1mach(2) / 12.0), 
                                   -math.log(12.0 * _d1mach(1))))
    
    if x < 10.0:
        # Error case: X must be >= 10, but we return a reasonable value or 0
        return 0.0
    
    if x >= _XMAX_LGMC:
        # Underflow case
        return 0.0
    
    if x < _XBIG:
        # Use Chebyshev series
        return _dcsevl(2.0 * (10.0 / x) ** 2 - 1.0, algmcs, _NALGM) / x
    else:
        # Simple approximation
        return 1.0 / (12.0 * x)


# =============================================================================
# DGAMLM: Compute minimum and maximum bounds for Gamma function
# =============================================================================

_DGAMLM_INITIALIZED = False
_XMIN_GAMMA = None
_XMAX_GAMMA = None

def _dgamlm():
    """
    Compute XMIN and XMAX bounds for Gamma function.
    Returns (XMIN, XMAX).
    """
    global _DGAMLM_INITIALIZED, _XMIN_GAMMA, _XMAX_GAMMA
    
    if _DGAMLM_INITIALIZED:
        return _XMIN_GAMMA, _XMAX_GAMMA
    
    _DGAMLM_INITIALIZED = True
    
    alnsml = math.log(_d1mach(1))
    xmin = -alnsml
    
    # Iterate to find XMIN (Newton-like iteration, 10 steps max)
    for _ in range(10):
        xold = xmin
        xln = math.log(xmin)
        xmin = xmin - xmin * ((xmin + 0.5) * xln - xmin - 0.2258 + alnsml) / (xmin * xln + 0.5)
        if abs(xmin - xold) < 0.005:
            break
    
    xmin = -xmin + 0.01
    
    alnbig = math.log(_d1mach(2))
    xmax = alnbig
    
    # Iterate to find XMAX (Newton-like iteration, 10 steps max)
    for _ in range(10):
        xold = xmax
        xln = math.log(xmax)
        xmax = xmax - xmax * ((xmax - 0.5) * xln - xmax + 0.9189 - alnbig) / (xmax * xln - 0.5)
        if abs(xmax - xold) < 0.005:
            break
    
    xmax = xmax - 0.01
    xmin = max(xmin, -xmax + 1.0)
    
    _XMIN_GAMMA = xmin
    _XMAX_GAMMA = xmax
    return xmin, xmax


# =============================================================================
# DGAMMA: Compute the complete Gamma function
# =============================================================================

_DGAMMA_INITIALIZED = False
_NGAM = None
_DGAMMA_XMIN = None
_DGAMMA_XMAX = None
_DGAMMA_DXREL = None

def _dgamma(x):
    """
    Compute the complete Gamma function for double precision argument X.
    Uses Chebyshev series for |X| <= 10, Stirling's formula for |X| > 10.
    """
    global _DGAMMA_INITIALIZED, _NGAM, _DGAMMA_XMIN, _DGAMMA_XMAX, _DGAMMA_DXREL
    
    # Chebyshev coefficients for GAM series (42 terms)
    gamcs = [
        +.8571195590989331421e-2,
        +.4415381324841006757e-2,
        +.5685043681599363786e-1,
        -.4219835396418560501e-2,
        +.1326808181212460220e-2,
        -.1893024529798880432e-3,
        +.3606925327441255266e-4,
        -.6056761904468416195e-5,
        +.1055829546302283347e-5,
        -.1811967365542100220e-6,
        +.3117724964715220777e-7,
        -.5354219639019687568e-8,
        +.9193275519859589468e-9,
        -.1577941280883439765e-9,
        +.2707980622934954545e-10,
        -.4646818653827948944e-11,
        +.7973350192007419656e-12,
        -.1368078209830920260e-12,
        +.2347319486553568520e-13,
        -.4027432614949066327e-14,
        +.6910051747372109013e-15,
        -.1185584500221929001e-15,
        +.2034148542496830415e-16,
        -.3490054341717405849e-17,
        +.5987993856485670595e-18,
        -.1027378057872228074e-18,
        +.1762702816060529825e-19,
        -.3024320653734306260e-20,
        +.5188914660218379397e-21,
        -.8902770842456576692e-22,
        +.1527474068493342602e-22,
        -.2620731256187362620e-23,
        +.4496464047830530613e-24,
        -.7714712731336877117e-25,
        +.1323635453126044036e-25,
        -.2270999412943013701e-26,
        +.3896418998003991449e-27,
        -.6685198115125953327e-28,
        +.1146998663140024384e-28,
        -.1967938586134674677e-29,
        +.3376448816585338090e-30,
        -.5793070335782135784e-31
    ]
    
    pi = 3.141592653589793238
    sq2pil = 0.9189385332046727418
    
    if not _DGAMMA_INITIALIZED:
        _DGAMMA_INITIALIZED = True
        _NGAM = _initds(gamcs, 42, 0.1 * _d1mach(3))
        _DGAMMA_XMIN, _DGAMMA_XMAX = _dgamlm()
        _DGAMMA_DXREL = math.sqrt(_d1mach(4))
    
    y = abs(x)
    
    if y > 10.0:
        # Stirling's formula for large |X|
        if x > _DGAMMA_XMAX:
            return float('inf')  # Overflow
        
        if x < _DGAMMA_XMIN:
            return 0.0  # Underflow
        
        # dgamma = exp((y - 0.5) * log(y) - y + sq2pil + d9lgmc(y))
        result = math.exp((y - 0.5) * math.log(y) - y + sq2pil + _d9lgmc(y))
        
        if x > 0.0:
            return result
        
        # Negative X: use reflection formula
        sinpiy = math.sin(pi * y)
        if sinpiy == 0.0:
            return float('inf')  # X is a negative integer
        
        return -pi / (y * sinpiy * result)
    
    # For |X| <= 10: use Chebyshev series
    n = int(x)
    if x < 0.0:
        n = n - 1
    y_frac = x - n
    n = n - 1
    
    # Evaluate Chebyshev series: 0.9375 + DCSEVL(2*y_frac - 1, GAMCS, NGAM)
    dgamma_val = 0.9375 + _dcsevl(2.0 * y_frac - 1.0, gamcs, _NGAM)
    
    if n == 0:
        return dgamma_val
    
    if n > 0:
        # Compute GAMMA(X) for X >= 2.0: multiply by (y_frac + 1), (y_frac + 2), ..., (y_frac + n)
        for i in range(1, n + 1):
            dgamma_val = (y_frac + i) * dgamma_val
        return dgamma_val
    
    # n < 0: Compute GAMMA(X) for X < 1.0: divide by x, x+1, ..., x+(-n-1)
    n = -n
    if x == 0.0:
        return float('inf')  # X is 0
    
    for i in range(1, n + 1):
        dgamma_val = dgamma_val / (x + i - 1)
    
    return dgamma_val


# =============================================================================
# DLNGAM: Logarithm of absolute value of Gamma function
# =============================================================================

_DLNGAM_INITIALIZED = False
_DLNGAM_XMAX = None
_DLNGAM_DXREL = None

def _dlngam(x):
    """
    Compute the logarithm of the absolute value of the Gamma function.
    For |X| <= 10, uses DGAMMA directly.
    For |X| > 10, uses Stirling-based formula with D9LGMC.
    """
    global _DLNGAM_INITIALIZED, _DLNGAM_XMAX, _DLNGAM_DXREL
    
    sq2pil = 0.9189385332046727418
    sqpi2l = 0.2257913526447274236
    pi = 3.141592653589793238
    
    if not _DLNGAM_INITIALIZED:
        _DLNGAM_INITIALIZED = True
        temp = 1.0 / math.log(_d1mach(2))
        _DLNGAM_XMAX = temp * _d1mach(2)
        _DLNGAM_DXREL = math.sqrt(_d1mach(4))
    
    y = abs(x)
    
    if y <= 10.0:
        # For |X| <= 10: take log of |DGAMMA(X)|
        g = _dgamma(x)
        return math.log(abs(g))
    
    # For |X| > 10
    if y > _DLNGAM_XMAX:
        return float('inf')  # Overflow
    
    if x > 0.0:
        # dlngam = sq2pil + (x - 0.5) * log(x) - x + d9lgmc(y)
        return sq2pil + (x - 0.5) * math.log(x) - x + _d9lgmc(y)
    
    # For x < 0, use reflection formula
    sinpiy = abs(math.sin(pi * y))
    
    if sinpiy == 0.0:
        return float('inf')  # X is a negative integer
    
    # dlngam = sqpi2l + (x - 0.5) * log(y) - x - log(sinpiy) - d9lgmc(y)
    return sqpi2l + (x - 0.5) * math.log(y) - x - math.log(sinpiy) - _d9lgmc(y)


# =============================================================================
# DLGAMS: Log of absolute value of Gamma and sign
# =============================================================================

def _dlgams(x):
    """
    Compute log of |GAMMA(X)| and sign of GAMMA(X).
    Returns (dlgam, sgngam) where:
      dlgam = log(|GAMMA(X)|)
      sgngam = sign(GAMMA(X)) = +1.0 or -1.0
    """
    dlgam = _dlngam(x)
    sgngam = 1.0
    
    if x <= 0.0:
        # For x <= 0, determine sign based on parity of -AINT(X)
        int_part = int(x)
        # MOD(-AINT(X), 2.0D0) gives 0 or 1
        # If result is 0 (even), sgngam = -1
        mod_result = abs(int_part) % 2
        if mod_result == 0:
            sgngam = -1.0
    
    return dlgam, sgngam


# =============================================================================
# DGAMR: Reciprocal of the Gamma function
# =============================================================================

def dgamr(x):
    """
    Compute the reciprocal of the Gamma function.
    Returns 1 / GAMMA(X).
    
    For |X| <= 10: uses DGAMMA directly.
    For |X| > 10: uses DLGAMS (log-based computation) to avoid overflow/underflow.
    """
    if x <= 0.0 and int(x) == x:
        # X is 0 or a negative integer: GAMMA is undefined or infinite
        return 0.0
    
    if abs(x) <= 10.0:
        # Direct computation via DGAMMA
        g = _dgamma(x)
        if g == 0.0:
            return float('inf')
        return 1.0 / g
    
    # For |X| > 10: use logarithmic computation
    alngx, sgngx = _dlgams(x)
    # dgamr = sgngx * exp(-alngx)
    return sgngx * math.exp(-alngx)
