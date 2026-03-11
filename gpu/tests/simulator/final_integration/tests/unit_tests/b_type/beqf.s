START:
    csrr  x3, x0
    lli   x5, 32
    lli   x6, 4
    lui   x7, 0x10

    slt x12, x3, x5
    bne p2, x12, x0, pred

    mul   x9,  x3, x6, 2
    add   x10, x7, x9, 2

    ; f1 = float(TID)
    itof  x8, x3, 2

    ; f0 = 0.0 (use x0 bits as 0.0)
    beq p3, x8, x0, 2

    lli   x11, 1, 3
    sw    x11, x10, 0, 3
    halt
