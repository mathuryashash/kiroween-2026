"""
DGAMR - Compute the reciprocal of the Gamma function.

Ported from SLATEC FNLIB (public domain).
"""

import math


# D1MACH constants (IEEE double-precision)
D1MACH_1 = 2.2250738585072014e-308  # smallest positive normal
D1MACH_2 = 1.7976931348623157e+308  # largest finite double
D1MACH_3 = 2.0 ** -53               # smallest relative spacing
D1MACH_4 = 2.0 ** -52               # largest relative spacing


# Module-level initialization flags and computed constants
_DGAMMA_INITIALIZED = False
_NGAM = None
_XMIN_GAMMA = None
_XMAX_GAMMA = None
_DXREL_GAMMA = None

_D9LGMC_INITIALIZED = False
_NALGM = None
_XBIG_D9LGMC = None
_XMAX_D9LGMC = None

_DLNGAM_INITIALIZED = False
_XMAX_DLNGAM = None
_DXREL_DLNGAM = None


def initds(os, nos, eta):
    """
    Initialize the orthogonal series so that INITDS is the number of terms
    needed to ensure the error is no larger than ETA.
    """
    if nos < 1:
        # Error: number of coefficients is less than 1
        return nos
    
    err = 0.0
    i = nos
    for ii in range(1, nos + 1):
        i = nos + 1 - ii
        err = err + abs(os[i - 1])  # Convert to 0-based indexing
        if err > eta:
            break
    
    if i == nos:
        # Warning: Chebyshev series too short for specified accuracy
        pass
    
    return i


def dcsevl(x, cs, n):
    """
    Evaluate the N-term Chebyshev series CS at X.
    Uses Clenshaw's recurrence.
    """
    # ONEPL computed on first call
    if not hasattr(dcsevl, 'onepl'):
        dcsevl.onepl = 1.0 + D1MACH_4
    
    if n < 1:
        # Error: number of terms <= 0
        pass
    if n > 1000:
        # Error: number of terms > 1000
        pass
    if abs(x) > dcsevl.onepl:
        # Warning: X outside the interval (-1, +1)
        pass
    
    b1 = 0.0
    b0 = 0.0
    twox = 2.0 * x
    for i in range(1, n + 1):
        b2 = b1
        b1 = b0
        ni = n + 1 - i
        b0 = twox * b1 - b2 + cs[ni - 1]  # Convert to 0-based indexing
    
    return 0.5 * (b0 - b2)


def dgamlm():
    """
    Calculate the minimum and maximum legal bounds for X in gamma(X).
    Returns (XMIN, XMAX).
    """
    alnsml = math.log(D1MACH_1)
    xmin = -alnsml
    for i in range(1, 11):
        xold = xmin
        xln = math.log(xmin)
        xmin = xmin - xmin * ((xmin + 0.5) * xln - xmin - 0.2258 + alnsml) / (xmin * xln + 0.5)
        if abs(xmin - xold) < 0.005:
            break
    
    xmin = -xmin + 0.01
    
    alnbig = math.log(D1MACH_2)
    xmax = alnbig
    for i in range(1, 11):
        xold = xmax
        xln = math.log(xmax)
        xmax = xmax - xmax * ((xmax - 0.5) * xln - xmax + 0.9189 - alnbig) / (xmax * xln - 0.5)
        if abs(xmax - xold) < 0.005:
            break
    
    xmax = xmax - 0.01
    xmin = max(xmin, -xmax + 1.0)
    
    return xmin, xmax


def d9lgmc(x):
    """
    Compute the log gamma correction factor for X >= 10.
    LOG(DGAMMA(X)) = LOG(SQRT(2*PI)) + (X-0.5)*LOG(X) - X + D9LGMC(X)
    """
    global _D9LGMC_INITIALIZED, _NALGM, _XBIG_D9LGMC, _XMAX_D9LGMC
    
    algmcs = [
        +.1666389480481863247205729650822e+0,
        -.1384948176067563840732986059135e-4,
        +.9810825646924729261571554748763e-8,
        -.1809129475572494194263306266719e-10,
        +.6221098041892605271260155434416e-13,
        -.3399615005417721944303330599666e-15,
        +.2683181998482698748957538846666e-17,
        -.2868042435334643284144622399999e-19,
        +.3962837061046434803679306666666e-21,
        -.6831888753985766870111999999999e-23,
        +.1429227355942498147573333333333e-24,
        -.3547598158101070547199999999999e-26,
        +.1025680058010470912000000000000e-27,
        -.3401102254316748799999999999999e-29,
        +.1276642195630062933333333333333e-30,
    ]
    
    if not _D9LGMC_INITIALIZED:
        _NALGM = initds(algmcs, 15, D1MACH_3)
        _XBIG_D9LGMC = 1.0 / math.sqrt(D1MACH_3)
        _XMAX_D9LGMC = math.exp(min(math.log(D1MACH_2 / 12.0), -math.log(12.0 * D1MACH_1)))
        _D9LGMC_INITIALIZED = True
    
    if x < 10.0:
        # Error: X must be >= 10
        pass
    if x >= _XMAX_D9LGMC:
        # Warning: X so big D9LGMC underflows
        return 0.0
    
    result = 1.0 / (12.0 * x)
    if x < _XBIG_D9LGMC:
        result = dcsevl(2.0 * (10.0 / x) ** 2 - 1.0, algmcs, _NALGM) / x
    
    return result


def dgamma(x):
    """
    Compute the complete Gamma function.
    """
    global _DGAMMA_INITIALIZED, _NGAM, _XMIN_GAMMA, _XMAX_GAMMA, _DXREL_GAMMA
    
    gamcs = [
        +.8571195590989931421920062399942e-2,
        +.4415381324841006757191577165272e-2,
        +.5685043681599336378632664588789e-1,
        -.4219835396418560501012500186624e-2,
        +.1326808181212460220584006796352e-2,
        -.1893024529798880432539470223865e-3,
        +.3606925327441245256578082217225e-4,
        -.6056761904460864284185548290365e-5,
        +.1055829546302283447318235090933e-5,
        -.1811967365542384082918558991166e-6,
        +.3117724964715322277902545931698e-7,
        -.5354219639019687140874081024347e-8,
        +.9193275519859894688778682594039e-9,
        -.1577941280288339761764232739395e-9,
        +.2707980622934954543266540330089e-10,
        -.4646818653825730144081661058933e-11,
        +.7973350192007419656407671753595e-12,
        -.1368078209830916025799499172309e-12,
        +.2347319486563800657233471718888e-13,
        -.4027432614949066932765705346999e-14,
        +.6910051747372100912138336975257e-15,
        -.1185584500221992907052387126192e-15,
        +.2034148542496373955201026051932e-16,
        -.3490054341717405849274012949108e-17,
        +.5987993856485305567135051066026e-18,
        -.1027378057872228074490069784431e-18,
        +.1762702816060529824942759660748e-19,
        -.3024320653735306260958772112042e-20,
        +.5188914660218397839717833550506e-21,
        -.8902770842456576692449251601066e-22,
        +.1527474068493342602274596891306e-22,
        -.2620731256187362900257328332799e-23,
        +.4496464047830538670331046566666e-24,
        -.7714712731336877911703901525333e-25,
        +.1323635453126044036465727146666e-25,
        -.2270999412942928816702313813333e-26,
        +.3896418998003991493208166399999e-27,
        -.6685198115125953327792127999999e-28,
        +.1146998663140024384347613866666e-28,
        -.1967938586345134677295103999999e-29,
        +.3376448816585338090334890666666e-30,
        -.5793070335782135784625493333333e-31,
    ]
    
    pi = 3.141592653589793238462643383279503
    sq2pil = 0.91893853320467274178032973640562
    
    if not _DGAMMA_INITIALIZED:
        _NGAM = initds(gamcs, 42, 0.1 * D1MACH_3)
        _XMIN_GAMMA, _XMAX_GAMMA = dgamlm()
        _DXREL_GAMMA = math.sqrt(D1MACH_4)
        _DGAMMA_INITIALIZED = True
    
    y = abs(x)
    if y > 10.0:
        # GAMMA(X) for ABS(X) > 10.0
        if x > _XMAX_GAMMA:
            # Error: X so big GAMMA overflows
            pass
        
        result = 0.0
        if x < _XMIN_GAMMA:
            # Warning: X so small GAMMA underflows
            return result
        
        result = math.exp((y - 0.5) * math.log(y) - y + sq2pil + d9lgmc(y))
        if x > 0.0:
            return result
        
        if abs((x - math.floor(x - 0.5)) / x) < _DXREL_GAMMA:
            # Warning: answer LT half precision, X too near negative integer
            pass
        
        sinpiy = math.sin(pi * y)
        if sinpiy == 0.0:
            # Error: X is a negative integer
            pass
        
        result = -pi / (y * sinpiy * result)
        return result
    
    # Compute GAMMA(X) for -XBND <= X <= XBND. Reduce interval and find
    # GAMMA(1+Y) for 0.0 <= Y < 1.0 first of all.
    n = int(x)
    if x < 0.0:
        n = n - 1
    y = x - n
    n = n - 1
    result = 0.9375 + dcsevl(2.0 * y - 1.0, gamcs, _NGAM)
    if n == 0:
        return result
    
    if n > 0:
        # GAMMA(X) for X >= 2.0 and X <= 10.0
        for i in range(1, n + 1):
            result = (y + i) * result
        return result
    
    # Compute GAMMA(X) for X < 1.0
    n = -n
    if x == 0.0:
        # Error: X is 0
        pass
    if x < 0.0 and x + n - 2 == 0.0:
        # Error: X is a negative integer
        pass
    if x < -0.5 and abs((x - math.floor(x - 0.5)) / x) < _DXREL_GAMMA:
        # Warning: answer LT half precision because X too near negative integer
        pass
    
    for i in range(1, n + 1):
        result = result / (x + i - 1)
    
    return result


def dlngam(x):
    """
    Compute the logarithm of the absolute value of the Gamma function.
    """
    global _DLNGAM_INITIALIZED, _XMAX_DLNGAM, _DXREL_DLNGAM
    
    sq2pil = 0.91893853320467274178032973640562
    sqpi2l = 0.22579135264472743236309761494411
    pi = 3.141592653589793238462643383279503
    
    if not _DLNGAM_INITIALIZED:
        temp = 1.0 / math.log(D1MACH_2)
        _XMAX_DLNGAM = temp * D1MACH_2
        _DXREL_DLNGAM = math.sqrt(D1MACH_4)
        _DLNGAM_INITIALIZED = True
    
    y = abs(x)
    if y <= 10.0:
        # LOG(ABS(DGAMMA(X))) for ABS(X) <= 10.0
        return math.log(abs(dgamma(x)))
    
    # LOG(ABS(DGAMMA(X))) for ABS(X) > 10.0
    if y > _XMAX_DLNGAM:
        # Error: ABS(X) so big DLNGAM overflows
        pass
    
    if x > 0.0:
        result = sq2pil + (x - 0.5) * math.log(x) - x + d9lgmc(y)
        return result
    
    sinpiy = abs(math.sin(pi * y))
    if sinpiy == 0.0:
        # Error: X is a negative integer
        pass
    
    if abs((x - math.floor(x - 0.5)) / x) < _DXREL_DLNGAM:
        # Warning: answer LT half precision because X too near negative integer
        pass
    
    result = sqpi2l + (x - 0.5) * math.log(y) - x - math.log(sinpiy) - d9lgmc(y)
    return result


def dlgams(x):
    """
    Compute the logarithm of the absolute value of the Gamma function
    and the sign of Gamma(X).
    Returns (DLGAM, SGNGAM).
    """
    dlgam = dlngam(x)
    sgngam = 1.0
    if x > 0.0:
        return dlgam, sgngam
    
    # Determine sign for negative X
    # Fixed for x=-28.56, x=11.36: AINT truncates toward zero, not floor toward -inf
    int_val = int((-(math.trunc(x))) % 2.0 + 0.1)
    if int_val == 0:
        sgngam = -1.0
    
    return dlgam, sgngam


def dgamr(x):
    """
    Compute the reciprocal of the Gamma function.
    
    DGAMR(X) calculates the double precision reciprocal of the
    complete Gamma function for double precision argument X.
    """
    # Return 0 for non-positive integers
    if x <= 0.0 and math.floor(x) == x:
        return 0.0
    
    # Fixed for x=11.36: use direct DGAMMA for all positive x (no overflow risk)
    # and |X| <= 10, use log-gamma only for negative x with |X| > 10
    if abs(x) <= 10.0 or x > 0.0:
        return 1.0 / dgamma(x)
    
    # For negative X with |X| > 10, use log-gamma to avoid underflow
    alngx, sgngx = dlgams(x)
    return sgngx * math.exp(-alngx)
