      REAL FUNCTION R1MACH(I)
      INTEGER I
C     Modern implementation using Fortran intrinsics
      IF (I .EQ. 1) R1MACH = TINY(1.0)
      IF (I .EQ. 2) R1MACH = HUGE(1.0)
      IF (I .EQ. 3) R1MACH = EPSILON(1.0)*0.5
      IF (I .EQ. 4) R1MACH = EPSILON(1.0)
      IF (I .EQ. 5) R1MACH = LOG10(2.0)
      RETURN
      END
