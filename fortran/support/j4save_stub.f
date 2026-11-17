C     J4SAVE stub (GALVANI). In SLATEC, J4SAVE stores the error-handler
C     state (error number, control flag, unit numbers). The harness XERMSG
C     stub never prints and never stops, so that state is never consulted:
C     this stub only lets XGETF, XSETF and XERCLR link. It keeps no state
C     and always returns 0.
      INTEGER FUNCTION J4SAVE (IWHICH, IVALUE, ISET)
      INTEGER IWHICH, IVALUE
      LOGICAL ISET
      J4SAVE = 0
      RETURN
      END
