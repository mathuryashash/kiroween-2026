      INTEGER FUNCTION I1MACH(I)
      INTEGER I
      IF (I .EQ. 1) I1MACH = 5   ! stdin unit
      IF (I .EQ. 2) I1MACH = 6   ! stdout unit  
      IF (I .EQ. 3) I1MACH = 7   ! punch unit
      IF (I .EQ. 4) I1MACH = 6   ! stderr unit
      IF (I .EQ. 5) I1MACH = 32  ! bits per integer
      IF (I .EQ. 6) I1MACH = 4   ! bytes per integer
      IF (I .EQ. 7) I1MACH = 2   ! base for integers
      IF (I .EQ. 8) I1MACH = 31  ! digits in integer (2^31-1)
      IF (I .EQ. 9) I1MACH = HUGE(1)  ! max integer
      IF (I .EQ. 10) I1MACH = 2  ! base for floats (FLT_RADIX)
      IF (I .EQ. 11) I1MACH = 24  ! single precision digits (mantissa bits)
      IF (I .EQ. 12) I1MACH = -125  ! single min exponent
      IF (I .EQ. 13) I1MACH = 128   ! single max exponent
      IF (I .EQ. 14) I1MACH = 53  ! double precision digits
      IF (I .EQ. 15) I1MACH = -1021  ! double min exponent
      IF (I .EQ. 16) I1MACH = 1024   ! double max exponent
      RETURN
      END
