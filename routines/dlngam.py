import math

# Constants for D1MACH(N)
_D1MACH_1 = 2.2250738585072014e-308  # Smallest positive normal
_D1MACH_2 = 1.7976931348623157e+308  # Largest finite double
_D1MACH_3 = 2.0 ** -53               # Smallest relative spacing
_D1MACH_4 = 2.0 ** -52               # Largest relative spacing

# Global state for first-call initialization
_DGAMMA_INITIALIZED = False
_DGAMMA_NGAM = None
_DGAMMA_XMIN = None
_DGAMMA_XMAX = None
_DGAMMA_DXREL = None
_DGAMMA_GAMCS = None

_D9LGMC_INITIALIZED = False
_D9LGMC_NALGM = None
_D9LGMC_XBIG = None
_D9LGMC_XMAX = None

_DCSEVL_INITIALIZED = False
_DCSEVL_ONEPL = None

_DLNGAM_INITIALIZED = False
_DLNGAM_SQ2PIL = None
_DLNGAM_SQPI2L = None
_DLNGAM_PI = None
_DLNGAM_XMAX = None
_DLNGAM_DXREL = None


def _initds(os, nos, eta):
    """
    Determine the number of terms needed in an orthogonal polynomial series
    so that it meets a specified accuracy.
    """
    if nos < 1:
        raise ValueError('Number of coefficients is less than 1')
    
    err = 0.0
    for ii in range(1, nos + 1):
        i = nos + 1 - ii
        err = err + abs(float(os[i - 1]))  # Adjust for 0-based indexing
        if err > eta:
            break
    
    if i == nos:
        raise ValueError('Chebyshev series too short for specified accuracy')
    
    return i


def _dcsevl(x, cs, n):
    """
    Evaluate the N-term Chebyshev series CS at X.
    Adapted from a method presented by Broucke.
    """
    global _DCSEVL_INITIALIZED, _DCSEVL_ONEPL
    
    if not _DCSEVL_INITIALIZED:
        _DCSEVL_ONEPL = 1.0 + _D1MACH_4
        _DCSEVL_INITIALIZED = True
    
    if n < 1:
        raise ValueError('NUMBER OF TERMS .LE. 0')
    if n > 1000:
        raise ValueError('NUMBER OF TERMS .GT. 1000')
    if abs(x) > _DCSEVL_ONEPL:
        raise ValueError('X OUTSIDE THE INTERVAL (-1,+1)')
    
    b1 = 0.0
    b0 = 0.0
    twox = 2.0 * x
    
    for i in range(1, n + 1):
        b2 = b1
        b1 = b0
        ni = n + 1 - i
        b0 = twox * b1 - b2 + cs[ni - 1]  # Adjust for 0-based indexing
    
    return 0.5 * (b0 - b2)


def _d9lgmc(x):
    """
    Compute the log Gamma correction factor so that
    LOG(DGAMMA(X)) = LOG(SQRT(2*PI)) + (X-0.5)*LOG(X) - X + D9LGMC(X).
    """
    global _D9LGMC_INITIALIZED, _D9LGMC_NALGM, _D9LGMC_XBIG, _D9LGMC_XMAX
    
    # Chebyshev coefficients for ALGM series
    algmcs = [
        0.1666389480 4518632472 0572965082 2e+0,
        -0.1384948176 0675638407 3298605913 5e-4,
        0.9810825646 9247294261 5717154748 7e-8,
        -0.1809129475 5724941942 6330626671 9e-10,
        0.6221098041 8926052271 2601554341 6e-13,
        -0.3399615005 4177219443 0333059966 6e-15,
        0.2683181998 4826987489 5753884666 6e-17,
        -0.2868042435 3346432841 4462239999 9e-19,
        0.3962837061 0464348036 7930666666 6e-21,
        -0.6831888753 9857668701 1199999999 9e-23,
        0.1429227355 9424981475 7333333333 3e-24,
        -0.3547598158 1010705471 9999999999 9e-26,
        0.1025680058 0104709120 0000000000 0e-27,
        -0.3401102254 3167487999 9999999999 9e-29,
        0.1276642195 6300629333 3333333333 3e-30,
    ]
    
    if not _D9LGMC_INITIALIZED:
        _D9LGMC_NALGM = _initds(algmcs, 15, float(_D1MACH_3))
        _D9LGMC_XBIG = 1.0 / math.sqrt(_D1MACH_3)
        _D9LGMC_XMAX = math.exp(min(math.log(_D1MACH_2 / 12.0), -math.log(12.0 * _D1MACH_1)))
        _D9LGMC_INITIALIZED = True
    
    if x < 10.0:
        raise ValueError('X MUST BE GE 10')
    
    if x >= _D9LGMC_XMAX:
        return 0.0
    
    result = 1.0 / (12.0 * x)
    if x < _D9LGMC_XBIG:
        result = _dcsevl(2.0 * (10.0 / x) ** 2 - 1.0, algmcs, _D9LGMC_NALGM) / x
    
    return result


def _dgamlm():
    """
    Calculate the minimum and maximum legal bounds for X in gamma(X).
    Returns (xmin, xmax).
    """
    alnsml = math.log(_D1MACH_1)
    xmin = -alnsml
    
    for _ in range(10):
        xold = xmin
        xln = math.log(xmin)
        xmin = xmin - xmin * ((xmin + 0.5) * xln - xmin - 0.2258 + alnsml) / (xmin * xln + 0.5)
        if abs(xmin - xold) < 0.005:
            break
    
    xmin = -xmin + 0.01
    
    alnbig = math.log(_D1MACH_2)
    xmax = alnbig
    
    for _ in range(10):
        xold = xmax
        xln = math.log(xmax)
        xmax = xmax - xmax * ((xmax - 0.5) * xln - xmax + 0.9189 - alnbig) / (xmax * xln - 0.5)
        if abs(xmax - xold) < 0.005:
            break
    
    xmax = xmax - 0.01
    xmin = max(xmin, -xmax + 1.0)
    
    return xmin, xmax


def _dgamma(x):
    """
    Compute the complete Gamma function for double precision argument X.
    """
    global _DGAMMA_INITIALIZED, _DGAMMA_NGAM, _DGAMMA_XMIN, _DGAMMA_XMAX, _DGAMMA_DXREL, _DGAMMA_GAMCS
    
    # Chebyshev series for GAM
    gamcs = [
        0.8571195590 9893314219 2006239994 2e-2,
        0.4415381324 8410067571 9131577165 2e-2,
        0.5685043681 5993633786 3266458878 9e-1,
        -0.4219835396 4185605010 1250018662 4e-2,
        0.1326808181 2124602205 8400679635 2e-2,
        -0.1893024529 7988804325 2394702388 6e-3,
        0.3606925327 4412452565 7808221722 5e-4,
        -0.6056761904 4608642184 8554829036 5e-5,
        0.1055829546 3022833447 3182350909 3e-5,
        -0.1811967365 5423840482 9185589116 6e-6,
        0.3117724964 7153222777 9025459316 9e-7,
        -0.5354219639 0196871408 7408102434 7e-8,
        0.9193275519 8595889468 8778682594 0e-9,
        -0.1577941280 2883397617 6742327395 3e-9,
        0.2707980622 9349545432 6654043308 9e-10,
        -0.4646818653 8257301440 8166105893 3e-11,
        0.7973350192 0074196564 6076717535 9e-12,
        -0.1368078209 8309160257 9949917230 9e-12,
        0.2347319486 5638006572 3347177168 8e-13,
        -0.4027432614 9490669327 6657053469 9e-14,
        0.6910051747 3721009121 3833697525 7e-15,
        -0.1185584500 2219929070 5238712619 2e-15,
        0.2034148542 4963739552 0102605193 2e-16,
        -0.3490054341 7174058492 7401294910 8e-17,
        0.5987993856 4853055671 3505106602 6e-18,
        -0.1027378057 8722280744 9006977843 1e-18,
        0.1762702816 0605298249 4275966074 8e-19,
        -0.3024320653 7353062609 5877211204 2e-20,
        0.5188914660 2183978397 1783355050 6e-21,
        -0.8902770842 4565766924 4925160106 6e-22,
        0.1527474068 4933426022 7459689130 6e-22,
        -0.2620731256 1873629002 5732833279 9e-23,
        0.4496464047 8305386703 3104657066 6e-24,
        -0.7714712731 3368779117 0390152533 3e-25,
        0.1323635453 1260440364 8657271466 6e-25,
        -0.2270999412 9429288167 0231381333 3e-26,
        0.3896418998 0039914493 2081663999 9e-27,
        -0.6685198115 1259533277 9212799999 9e-28,
        0.1146998663 1400243843 4761386666 6e-28,
        -0.1967938586 3451346772 9510399999 9e-29,
        0.3376448816 5853380903 3489066666 6e-30,
        -0.5793070335 7821357846 2549333333 3e-31,
    ]
    
    if not _DGAMMA_INITIALIZED:
        _DGAMMA_GAMCS = gamcs
        _DGAMMA_NGAM = _initds(gamcs, 42, 0.1 * float(_D1MACH_3))
        _DGAMMA_XMIN, _DGAMMA_XMAX = _dgamlm()
        _DGAMMA_DXREL = math.sqrt(_D1MACH_4)
        _DGAMMA_INITIALIZED = True
    
    pi = 3.1415926535 8979323846 2643383279 50
    sq2pil = 0.9189385332 0467274178 0329736405 62
    
    y = abs(x)
    
    if y <= 10.0:
        # COMPUTE GAMMA(X) FOR -XBND .LE. X .LE. XBND
        # Reduce interval and find GAMMA(1+Y) for 0.0 .LE. Y .LT. 1.0 first
        n = int(x)
        if x < 0.0:
            n = n - 1
        y_reduced = x - n
        n = n - 1
        result = 0.9375 + _dcsevl(2.0 * y_reduced - 1.0, _DGAMMA_GAMCS, _DGAMMA_NGAM)
        
        if n == 0:
            return result
        
        if n > 0:
            # GAMMA(X) FOR X .GE. 2.0 AND X .LE. 10.0
            for i in range(1, n + 1):
                result = (y_reduced + i) * result
            return result
        else:
            # COMPUTE GAMMA(X) FOR X .LT. 1.0
            n_abs = -n
            if x == 0.0:
                raise ValueError('X IS 0')
            if x < 0.0 and x + n_abs - 2 == 0.0:
                raise ValueError('X IS A NEGATIVE INTEGER')
            if x < -0.5 and abs((x - math.floor(x - 0.5)) / x) < _DGAMMA_DXREL:
                raise ValueError('ANSWER LT HALF PRECISION BECAUSE X TOO NEAR NEGATIVE INTEGER')
            
            for i in range(1, n_abs + 1):
                result = result / (x + i - 1)
            return result
    
    # GAMMA(X) FOR ABS(X) .GT. 10.0
    if x > _DGAMMA_XMAX:
        raise ValueError('X SO BIG GAMMA OVERFLOWS')
    
    result = 0.0
    if x < _DGAMMA_XMIN:
        raise ValueError('X SO SMALL GAMMA UNDERFLOWS')
    
    if x >= _DGAMMA_XMIN:
        result = math.exp((y - 0.5) * math.log(y) - y + sq2pil + _d9lgmc(y))
    
    if x > 0.0:
        return result
    
    # For negative x
    if abs((x - math.floor(x - 0.5)) / x) < _DGAMMA_DXREL:
        raise ValueError('ANSWER LT HALF PRECISION, X TOO NEAR NEGATIVE INTEGER')
    
    sinpiy = math.sin(pi * y)
    if sinpiy == 0.0:
        raise ValueError('X IS A NEGATIVE INTEGER')
    
    result = -pi / (y * sinpiy * result)
    
    return result


def dlngam(x: float) -> float:
    """
    Compute the logarithm of the absolute value of the Gamma function.
    DLNGAM(X) calculates the double precision logarithm of the
    absolute value of the Gamma function for double precision argument X.
    """
    global _DLNGAM_INITIALIZED, _DLNGAM_SQ2PIL, _DLNGAM_SQPI2L, _DLNGAM_PI, _DLNGAM_XMAX, _DLNGAM_DXREL
    
    if not _DLNGAM_INITIALIZED:
        _DLNGAM_SQ2PIL = 0.9189385332 0467274178 0329736405 62
        _DLNGAM_SQPI2L = 0.2257913526 4472743236 3097614947 441
        _DLNGAM_PI = 3.1415926535 8979323846 2643383279 50
        
        # Compute XMAX and DXREL
        temp = 1.0 / math.log(_D1MACH_2)
        _DLNGAM_XMAX = temp * _D1MACH_2
        _DLNGAM_DXREL = math.sqrt(_D1MACH_4)
        
        _DLNGAM_INITIALIZED = True
    
    y = abs(x)
    
    if y <= 10.0:
        # LOG (ABS (DGAMMA(X)) ) FOR ABS(X) .LE. 10.0
        return math.log(abs(_dgamma(x)))
    
    # LOG ( ABS (DGAMMA(X)) ) FOR ABS(X) .GT. 10.0
    if y > _DLNGAM_XMAX:
        raise ValueError('ABS(X) SO BIG DLNGAM OVERFLOWS')
    
    if x > 0.0:
        return _DLNGAM_SQ2PIL + (x - 0.5) * math.log(x) - x + _d9lgmc(y)
    
    # For x <= 0
    sinpiy = abs(math.sin(_DLNGAM_PI * y))
    if sinpiy == 0.0:
        raise ValueError('X IS A NEGATIVE INTEGER')
    
    if abs((x - math.floor(x - 0.5)) / x) < _DLNGAM_DXREL:
        raise ValueError('ANSWER LT HALF PRECISION BECAUSE X TOO NEAR NEGATIVE INTEGER')
    
    return _DLNGAM_SQPI2L + (x - 0.5) * math.log(y) - x - math.log(sinpiy) - _d9lgmc(y)
