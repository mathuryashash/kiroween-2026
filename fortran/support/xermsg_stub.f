C     XERMSG stub (GALVANI): never aborts, never prints.
C     LEVEL 2 is a fatal error in SLATEC (the real XERMSG stops the
C     program), so set the COMMON flag and the batch driver prints NaN.
C     LEVEL 0 and 1 are a warning and a recoverable error: SLATEC then
C     returns the value it computed, so the driver prints that value.
      SUBROUTINE XERMSG(LIBRAR, SUBROU, MESSG, NERR, LEVEL)
      CHARACTER*(*) LIBRAR, SUBROU, MESSG
      INTEGER NERR, LEVEL
      LOGICAL XERR_FLAG
      COMMON /XERMSG_FLAG/ XERR_FLAG
      IF (LEVEL .GE. 2) XERR_FLAG = .TRUE.
      RETURN
      END
