"""
DLNGAM - Compute the logarithm of the absolute value of the Gamma function.

Translated from SLATEC FNLIB Fortran source (public domain).
"""

import math


# D1MACH constants (IEEE 754 double precision)
D1MACH_1 = 2.2250738585072014e-308  # smallest positive normal
D1MACH_2 = 1.7976931348623157e+308  # largest finite double
D1MACH_3 = 2.0 ** -53               # smallest relative spacing
D1MACH_4 = 2.0 ** -52               # largest relative spacing


def _initds(os, nos, eta):
    """
    Initialize orthogonal series.
    Determine the number of terms needed so error is no larger than eta.
    
    Fortran INITDS from SLATEC.
    """
    if nos < 1:
        raise ValueError("INITDS: Number of coefficients is less than 1")
    
    err = 0.0
    for ii in range(1, nos + 1):
        i = nos + 1 - ii
        err = err + abs(os[i - 1])  # os is 0-based in Python
        if err > eta:
            if i == nos:
                raise ValueError("INITDS: Chebyshev series too short for specified accuracy")
            return i
    
    if nos == nos:  # loop completed without finding threshold
        raise ValueError("INITDS: Chebyshev series too short for specified accuracy")
    return nos


def _dcsevl(x, cs, n):
    """
    Evaluate N-term Chebyshev series CS at X.
    
    Fortran DCSEVL from SLATEC.
    In evaluating CS, only half the first coefficient is summed.
    """
    # First call initialization
    if not hasattr(_dcsevl, 'onepl'):
        _dcsevl.onepl = 1.0 + D1MACH_4
    
    if n < 1:
        raise ValueError("DCSEVL: NUMBER OF TERMS .LE. 0")
    if n > 1000:
        raise ValueError("DCSEVL: NUMBER OF TERMS .GT. 1000")
    if abs(x) > _dcsevl.onepl:
        raise ValueError("DCSEVL: X OUTSIDE THE INTERVAL (-1,+1)")
    
    b1 = 0.0
    b0 = 0.0
    twox = 2.0 * x
    for i in range(1, n + 1):
        b2 = b1
        b1 = b0
        ni = n + 1 - i
        b0 = twox * b1 - b2 + cs[ni - 1]  # cs is 0-based in Python
    
    return 0.5 * (b0 - b2)


def _d9lgmc(x):
    """
    Compute the log gamma correction factor for X >= 10.
    LOG(DGAMMA(X)) = LOG(SQRT(2*PI)) + (X-0.5)*LOG(X) - X + D9LGMC(X)
    
    Fortran D9LGMC from SLATEC.
    """
    algmcs = [
        +.1666389480451863247205729650822e+0,
        -.1384948176067563840732986059135e-4,
        +.9810825646924729261571715474870e-8,
        -.1809129475572494194263306266719e-10,
        +.6221098041892605271260155434416e-13,
        -.3399615005417721944303330599666e-15,
        +.2683181998482698748957538846666e-17,
        -.2868042435334643284144622399999e-19,
        +.3962837061046434803679306666666e-21,
        -.6831888753985766870111999999999e-23,
        +.1429227355942498175733333333333e-24,
        -.3547598158101070547199999999999e-26,
        +.1025680058010470912000000000000e-27,
        -.3401102254316748799999999999999e-29,
        +.1276642195630062933333333333333e-30,
    ]
    
    # First call initialization
    if not hasattr(_d9lgmc, 'nalgm'):
        _d9lgmc.nalgm = _initds(algmcs, 15, D1MACH_3)
        _d9lgmc.xbig = 1.0 / math.sqrt(D1MACH_3)
        _d9lgmc.xmax = math.exp(min(math.log(D1MACH_2 / 12.0), -math.log(12.0 * D1MACH_1)))
    
    if x < 10.0:
        raise ValueError("D9LGMC: X MUST BE GE 10")
    if x >= _d9lgmc.xmax:
        return 0.0
    
    result = 1.0 / (12.0 * x)
    if x < _d9lgmc.xbig:
        result = _dcsevl(2.0 * (10.0 / x) ** 2 - 1.0, algmcs, _d9lgmc.nalgm) / x
    
    return result


def _dgamlm():
    """
    Calculate the minimum and maximum legal bounds for X in DGAMMA(X).
    Returns (XMIN, XMAX).
    
    Fortran DGAMLM from SLATEC.
    """
    alnsml = math.log(D1MACH_1)
    xmin = -alnsml
    for i in range(1, 11):
        xold = xmin
        xln = math.log(xmin)
        xmin = xmin - xmin * ((xmin + 0.5) * xln - xmin - 0.2258 + alnsml) / (xmin * xln + 0.5)
        if abs(xmin - xold) < 0.005:
            break
    else:
        raise ValueError("DGAMLM: UNABLE TO FIND XMIN")
    
    xmin = -xmin + 0.01
    
    alnbig = math.log(D1MACH_2)
    xmax = alnbig
    for i in range(1, 11):
        xold = xmax
        xln = math.log(xmax)
        xmax = xmax - xmax * ((xmax - 0.5) * xln - xmax + 0.9189 - alnbig) / (xmax * xln - 0.5)
        if abs(xmax - xold) < 0.005:
            break
    else:
        raise ValueError("DGAMLM: UNABLE TO FIND XMAX")
    
    xmax = xmax - 0.01
    xmin = max(xmin, -xmax + 1.0)
    
    return xmin, xmax


def _dgamma(x):
    """
    Compute the complete Gamma function.
    
    Fortran DGAMMA from SLATEC.
    """
    gamcs = [
        +.8571195590989331421920062399942e-2,
        +.4415381324841006757191577165252e-2,
        +.5685043681599336378632664588789e-1,
        -.4219835396418560501012500186624e-2,
        +.1326808181212460220584006796352e-2,
        -.1893024529798880432539470238860e-3,
        +.3606925327441245256578082217225e-4,
        -.6056761904460864284855829036506e-5,
        +.1055829546302283447318235090930e-5,
        -.1811967365542384082918558991166e-6,
        +.3117724964715322277902545931690e-7,
        -.5354219639019687140874081024347e-8,
        +.9193275519859889468877868259400e-9,
        -.1577941280288339761767423273953e-9,
        +.2707980622934954543266540433089e-10,
        -.4646818653825730144081661058933e-11,
        +.7973350192007419656407671753590e-12,
        -.1368078209830916025794991723090e-12,
        +.2347319486563800657233471716880e-13,
        -.4027432614949066932765705346990e-14,
        +.6910051747372100912138336975257e-15,
        -.1185584500221992907052387126192e-15,
        +.2034148542496373955201026051932e-16,
        -.3490054341717405849274012949108e-17,
        +.5987993856485305567135051066026e-18,
        -.1027378057872228074490069778431e-18,
        +.1762702816060529824942759660748e-19,
        -.3024320653735306260958772112042e-20,
        +.5188914660218397839717833550506e-21,
        -.8902770842456576692449251601066e-22,
        +.1527474068493342602274596891306e-22,
        -.2620731256187362900257328332799e-23,
        +.4496464047830538670331046570666e-24,
        -.7714712731336877911703901525333e-25,
        +.1323635453126044036486572714666e-25,
        -.2270999412942928816702313813333e-26,
        +.3896418998003991493208166399999e-27,
        -.6685198115125953327792127999999e-28,
        +.1146998663140024384347613866666e-28,
        -.1967938586345134677291039999999e-29,
        +.3376448816585338090334890666666e-30,
        -.5793070335782135784625493333333e-31,
    ]
    
    pi = 3.141592653589793238462643383279e0
    sq2pil = 0.918938533204672741780329736406e0
    
    # First call initialization
    if not hasattr(_dgamma, 'ngam'):
        _dgamma.ngam = _initds(gamcs, 42, 0.1 * D1MACH_3)
        _dgamma.xmin, _dgamma.xmax = _dgamlm()
        _dgamma.dxrel = math.sqrt(D1MACH_4)
    
    y = abs(x)
    if y <= 10.0:
        # COMPUTE GAMMA(X) FOR -XBND .LE. X .LE. XBND.
        # REDUCE INTERVAL AND FIND GAMMA(1+Y) FOR 0.0 .LE. Y .LT. 1.0 FIRST OF ALL.
        n = int(x)
        if x < 0.0:
            n = n - 1
        y = x - n
        n = n - 1
        result = 0.9375 + _dcsevl(2.0 * y - 1.0, gamcs, _dgamma.ngam)
        
        if n == 0:
            return result
        
        if n > 0:
            # GAMMA(X) FOR X .GE. 2.0 AND X .LE. 10.0
            for i in range(1, n + 1):
                result = (y + i) * result
            return result
        
        # COMPUTE GAMMA(X) FOR X .LT. 1.0
        n = -n
        if x == 0.0:
            raise ValueError("DGAMMA: X IS 0")
        if x < 0.0 and x + n - 2 == 0.0:
            raise ValueError("DGAMMA: X IS A NEGATIVE INTEGER")
        if x < -0.5 and abs((x - int(x - 0.5)) / x) < _dgamma.dxrel:
            # AINT(X - 0.5) in Fortran truncates toward zero
            pass  # Warning would go here
        
        for i in range(1, n + 1):
            result = result / (x + i - 1)
        return result
    
    # GAMMA(X) FOR ABS(X) .GT. 10.0.  RECALL Y = ABS(X).
    if x > _dgamma.xmax:
        raise ValueError("DGAMMA: X SO BIG GAMMA OVERFLOWS")
    
    if x < _dgamma.xmin:
        return 0.0
    
    result = math.exp((y - 0.5) * math.log(y) - y + sq2pil + _d9lgmc(y))
    if x > 0.0:
        return result
    
    if abs((x - int(x - 0.5)) / x) < _dgamma.dxrel:
        # AINT(X - 0.5) in Fortran truncates toward zero
        pass  # Warning would go here
    
    sinpiy = math.sin(pi * y)
    if sinpiy == 0.0:
        raise ValueError("DGAMMA: X IS A NEGATIVE INTEGER")
    
    return -pi / (y * sinpiy * result)


def dlngam(x):
    """
    Compute the logarithm of the absolute value of the Gamma function.
    
    DLNGAM(X) calculates the double precision logarithm of the
    absolute value of the Gamma function for double precision argument X.
    
    Translated from SLATEC FNLIB Fortran source (public domain).
    """
    sq2pil = 0.918938533204672741780329736406e0
    sqpi2l = 0.225791352644727432363097614947e0
    pi = 3.141592653589793238462643383279e0
    
    # First call initialization
    if not hasattr(dlngam, 'xmax'):
        temp = 1.0 / math.log(D1MACH_2)
        dlngam.xmax = temp * D1MACH_2
        dlngam.dxrel = math.sqrt(D1MACH_4)
    
    y = abs(x)
    if y <= 10.0:
        # LOG (ABS (DGAMMA(X)) ) FOR ABS(X) .LE. 10.0
        return math.log(abs(_dgamma(x)))
    
    # LOG ( ABS (DGAMMA(X)) ) FOR ABS(X) .GT. 10.0
    if y > dlngam.xmax:
        raise ValueError("DLNGAM: ABS(X) SO BIG DLNGAM OVERFLOWS")
    
    if x > 0.0:
        result = sq2pil + (x - 0.5) * math.log(x) - x + _d9lgmc(y)
        return result
    
    sinpiy = abs(math.sin(pi * y))
    if sinpiy == 0.0:
        raise ValueError("DLNGAM: X IS A NEGATIVE INTEGER")
    
    if abs((x - int(x - 0.5)) / x) < dlngam.dxrel:
        # AINT(X - 0.5) in Fortran truncates toward zero - warning about precision loss
        pass
    
    result = sqpi2l + (x - 0.5) * math.log(y) - x - math.log(sinpiy) - _d9lgmc(y)
    return result
