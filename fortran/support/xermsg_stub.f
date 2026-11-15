C     XERMSG stub: sets COMMON flag and returns (never aborts).
C     GALVANI harness uses this so the driver can detect errors and
C     print NaN without terminating the batch.
      SUBROUTINE XERMSG(LIBRAR, SUBROU, MESSG, NERR, LEVEL)
      CHARACTER*(*) LIBRAR, SUBROU, MESSG
      INTEGER NERR, LEVEL
      LOGICAL XERR_FLAG
      COMMON /XERMSG_FLAG/ XERR_FLAG
      XERR_FLAG = .TRUE.
      RETURN
      END
