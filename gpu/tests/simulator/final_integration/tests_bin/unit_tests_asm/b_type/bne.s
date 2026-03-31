START:
    csrr  x3, 0
    lli   x5, 32
    lli   x6, 4
    lui   x7, 0x10

    slt x13, x3, x5
    bne 2, x13, x0, 0

    mul   x9,  x3, x6, 2
    add   x10, x7, x9, 2

    ; default = 0
    sw    x0, 0(x10), 2

    ; if (TID != 0) store 1
    bne   3, x3, x0, 2

    lli   x11, 1, 3
    sw    x11, 0(x10), 3
    halt
