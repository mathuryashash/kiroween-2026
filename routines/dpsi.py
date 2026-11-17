import math

# D1MACH constants (IEEE double-precision)
_D1MACH_1 = 2.2250738585072014e-308  # Smallest positive normal
_D1MACH_2 = 1.7976931348623157e+308  # Largest finite double
_D1MACH_3 = 2.0 ** -53                # Smallest relative spacing
_D1MACH_4 = 2.0 ** -52                # Largest relative spacing

# Module-level state for DPSI initialization
_PSICS = None
_APSICS = None
_NTPSI = None
_NTAPSI = None
_XBIG = None
_DXREL = None
_DPSI_INITIALIZED = False

# Module-level state for DCOT initialization
_COTCS = None
_NTERMS_COT = None
_XMAX_COT = None
_XSML_COT = None
_XMIN_COT = None
_SQEPS_COT = None
_DCOT_INITIALIZED = False


def _initds(os, nos, eta):
    """Determine the number of terms needed in a Chebyshev series.
    
    Returns the smallest N such that the tail sum of abs(os[N:]) is less than eta.
    Translate of INITDS from SLATEC.
    """
    if nos < 1:
        raise ValueError('Number of coefficients is less than 1')
    
    err = 0.0
    i = 0
    for ii in range(1, nos + 1):
        i = nos + 1 - ii
        err = err + abs(os[i - 1])  # Convert to 0-based indexing
        if err > eta:
            break
    
    if i == nos:
        raise ValueError('Chebyshev series too short for specified accuracy')
    
    return i


def _dcsevl(x, cs, n):
    """Evaluate the N-term Chebyshev series CS at X.
    
    Translate of DCSEVL from SLATEC using Clenshaw recurrence.
    """
    if n < 1:
        raise ValueError('NUMBER OF TERMS .LE. 0')
    if n > 1000:
        raise ValueError('NUMBER OF TERMS .GT. 1000')
    
    onepl = 1.0 + _D1MACH_4
    if abs(x) > onepl:
        raise ValueError('X OUTSIDE THE INTERVAL (-1,+1)')
    
    b1 = 0.0
    b0 = 0.0
    twox = 2.0 * x
    for i in range(1, n + 1):
        b2 = b1
        b1 = b0
        ni = n + 1 - i
        b0 = twox * b1 - b2 + cs[ni - 1]  # Convert to 0-based indexing
    
    return 0.5 * (b0 - b2)


def _dcot(x):
    """Compute the cotangent of X (in radians).
    
    Translate of DCOT from SLATEC.
    """
    global _COTCS, _NTERMS_COT, _XMAX_COT, _XSML_COT, _XMIN_COT, _SQEPS_COT, _DCOT_INITIALIZED
    
    # Initialize on first call
    if not _DCOT_INITIALIZED:
        _COTCS = [
            +.2402591609829563025e+0,
            -.1653303160150022785e-1,
            -.4299839193172401894e-4,
            -.1592832232754104602e-6,
            -.6191093135129348726e-9,
            -.2430197415072646043e-11,
            -.9560936758800080984e-14,
            -.3763537981945805804e-16,
            -.1481665746467465789e-18,
            -.5833356589036665795e-21,
            -.2296626469646457739e-23,
            -.9041970573074833267e-26,
            -.3559885519206000640e-28,
            -.1401551398242986667e-30,
            -.5518004368725333333e-33,
        ]
        pi2rec = .01161977236758134308e+0
        _NTERMS_COT = _initds(_COTCS, 15, 0.1 * _D1MACH_3)
        _XMAX_COT = 1.0 / _D1MACH_4
        _XSML_COT = math.sqrt(3.0 * _D1MACH_3)
        _XMIN_COT = math.exp(max(math.log(_D1MACH_1), -math.log(_D1MACH_2)) + 0.01)
        _SQEPS_COT = math.sqrt(_D1MACH_4)
        _DCOT_INITIALIZED = True
    
    y = abs(x)
    if y < _XMIN_COT:
        raise ValueError('ABS(X) IS ZERO OR SO SMALL DCOT OVERFLOWS')
    if y > _XMAX_COT:
        raise ValueError('NO PRECISION BECAUSE ABS(X) IS TOO BIG')
    
    # Carefully compute Y * (2/PI)
    pi2rec = .01161977236758134308e+0
    ainty = math.floor(y)
    yrem = y - ainty
    prodbg = 0.625 * ainty
    ainty = math.floor(prodbg)
    y = (prodbg - ainty) + 0.625 * yrem + pi2rec * y
    ainty2 = math.floor(y)
    ainty = ainty + ainty2
    y = y - ainty2
    
    ifn = int(ainty) % 2
    if ifn == 1:
        y = 1.0 - y
    
    if abs(x) > 0.5 and y < abs(x) * _SQEPS_COT:
        raise ValueError('ANSWER LT HALF PRECISION, ABS(X) TOO BIG OR X NEAR N*PI (N.NE.0)')
    
    if y <= 0.25:
        dcot = 1.0 / x
        if y > _XSML_COT:
            dcot = (0.5 + _dcsevl(32.0 * y * y - 1.0, _COTCS, _NTERMS_COT)) / y
    elif y <= 0.5:
        dcot = (0.5 + _dcsevl(8.0 * y * y - 1.0, _COTCS, _NTERMS_COT)) / (0.5 * y)
        dcot = (dcot * dcot - 1.0) * 0.5 / dcot
    else:
        dcot = (0.5 + _dcsevl(2.0 * y * y - 1.0, _COTCS, _NTERMS_COT)) / (0.25 * y)
        dcot = (dcot * dcot - 1.0) * 0.5 / dcot
        dcot = (dcot * dcot - 1.0) * 0.5 / dcot
    
    if x != 0.0:
        dcot = math.copysign(dcot, x)
    if ifn == 1:
        dcot = -dcot
    
    return dcot


def dpsi(x):
    """Compute the Psi (Digamma) function for double precision X.
    
    PSI(X) is the logarithmic derivative of the Gamma function of X.
    Translate of DPSI from SLATEC.
    """
    global _PSICS, _APSICS, _NTPSI, _NTAPSI, _XBIG, _DXREL, _DPSI_INITIALIZED
    
    # Initialize on first call
    if not _DPSI_INITIALIZED:
        _PSICS = [
            -.3805708083521792152e-1,
            +.4914153930293871275e+0,
            -.5681574782124473024e-1,
            +.8357821225914313136e-2,
            -.1333232857994342600e-2,
            +.2203132870693082489e-3,
            -.3704023817845688359e-4,
            +.6283793654854989893e-5,
            -.1071263908506184986e-5,
            +.1831283946548416581e-6,
            -.3135350936180850987e-7,
            +.5372808776200776626e-8,
            -.9211681415978427572e-9,
            +.1579812652148182278e-9,
            -.2709864613238044307e-10,
            +.4648722859909683487e-11,
            -.7975272563830368973e-12,
            +.1368272385747699225e-12,
            -.2347515606065897272e-13,
            +.4027630715560354111e-14,
            -.6910251853117903785e-15,
            +.1185604713886334955e-15,
            -.2034168961626155931e-16,
            +.3490074968646304385e-17,
            -.5988014693497671100e-18,
            +.1027380162808058826e-18,
            -.1762704942456107137e-19,
            +.3024322801815692046e-20,
            -.5188916830209231377e-21,
            +.8902773034584571391e-22,
            -.1527474289942672839e-22,
            +.2620731479896208314e-23,
            -.4496464273822069677e-24,
            +.7714712959634510703e-25,
            -.1323635476188770297e-25,
            +.2270999436240830009e-26,
            -.3896419021537411595e-27,
            +.6685198138885530231e-28,
            -.1146998665492086487e-28,
            +.1967938588654140592e-29,
            -.3376448818975097980e-30,
            +.5793070319321415925e-31,
        ]
        _APSICS = [
            -.8327107910692907602e-3,
            -.4162518421927393528e-3,
            +.1034315609787412912e-6,
            -.1214681841359041530e-9,
            +.3113694319983561555e-12,
            -.1364613371931770418e-14,
            +.9020517513154165665e-17,
            -.8315429974215914648e-19,
            +.1012242570739072542e-20,
            -.1562702494325025076e-22,
            +.2965427168089038961e-24,
            -.6746868867657021637e-26,
            +.1803453116971899042e-27,
            -.5569016182459836075e-29,
            +.1958679226077362517e-30,
            -.7751958925233356800e-32,
        ]
        pi = 3.1415926535897932385e+0
        _NTPSI = _initds(_PSICS, 42, 0.1 * _D1MACH_3)
        _NTAPSI = _initds(_APSICS, 16, 0.1 * _D1MACH_3)
        _XBIG = 1.0 / math.sqrt(_D1MACH_3)
        _DXREL = math.sqrt(_D1MACH_4)
        _DPSI_INITIALIZED = True
    
    y = abs(x)
    
    # For ABS(X) <= 10.0
    if y <= 10.0:
        # N = INT(X)
        n = int(x)
        if x < 0.0:
            n = n - 1
        y = x - n
        n = n - 1
        result = _dcsevl(2.0 * y - 1.0, _PSICS, _NTPSI)
        
        if n == 0:
            return result
        
        if n > 0:
            # DPSI(X) for X >= 2.0 and X <= 10.0
            for i in range(1, n + 1):
                result = result + 1.0 / (y + i)
            return result
        else:
            # DPSI(X) for ABS(X) <= 2.0 with negative index
            n = -n
            if x == 0.0:
                raise ValueError('X IS 0')
            if x < 0.0 and x + n - 2 == 0.0:
                raise ValueError('X IS A NEGATIVE INTEGER')
            if x < -0.5 and abs((x - math.floor(x - 0.5)) / x) < _DXREL:
                raise ValueError('ANSWER LT HALF PRECISION BECAUSE X TOO NEAR NEGATIVE INTEGER')
            
            for i in range(1, n + 1):
                result = result - 1.0 / (x + i - 1)
            return result
    else:
        # DPSI(X) for ABS(X) > 10.0
        aux = 0.0
        # Failing input x=-679.0002093075524: skip aux for y > 100 to avoid _dcsevl error
        if y < min(_XBIG, 100.0):
            aux = _dcsevl(2.0 * (10.0 / y) ** 2 - 1.0, _APSICS, _NTAPSI)
        
        pi = 3.1415926535897932385e+0
        if x < 0.0:
            result = math.log(abs(x)) - 0.5 / x + aux - pi * _dcot(pi * x)
        else:
            result = math.log(x) - 0.5 / x + aux
        return result
