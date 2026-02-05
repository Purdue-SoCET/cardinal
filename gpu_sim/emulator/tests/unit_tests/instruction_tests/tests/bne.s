START:
    csrr  x3, x0
    lli   x5, 32
    lli   x6, 4
    lui   x7, 0x10

    blt   p2, x3, x5, pred

    mul   x9,  x3, x6, 2
    add   x10, x7, x9, 2

    ; default = 0
    sw    x0, x10, 0, 2

    ; if (TID != 0) store 1
    bne   TAKEN, x3, x0, 2

    halt

TAKEN:
    lli   x11, 1, 2
    sw    x11, x10, 0, 2
    halt
