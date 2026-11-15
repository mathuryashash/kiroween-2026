      DOUBLE PRECISION FUNCTION D1MACH(I)
      INTEGER I
C     IEEE double constants via Fortran intrinsics (replaces the 1978 machine table)
      D1MACH = 0.0D0
      IF (I .EQ. 1) D1MACH = TINY(1.0D0)
      IF (I .EQ. 2) D1MACH = HUGE(1.0D0)
      IF (I .EQ. 3) D1MACH = EPSILON(1.0D0)*0.5D0
      IF (I .EQ. 4) D1MACH = EPSILON(1.0D0)
      IF (I .EQ. 5) D1MACH = LOG10(2.0D0)
      RETURN
      END
