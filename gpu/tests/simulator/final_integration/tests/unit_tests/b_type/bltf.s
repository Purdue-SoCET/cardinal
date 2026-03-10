START:
    csrr  x3, x0
    lli   x5, 32
    lli   x6, 4
    lui   x7, 0x10

    slt x12, x3, x5
    bne p2, x12, x0, pred

    mul   x9,  x3, x6, 2
    add   x10, x7, x9, 2

    ; f1 = float(TID-16)
    addi  x3, x3, -16, 2
    itof  x8, x3, 2

    ; if (f1 < 0) store 1
    sltf x12, x8, x0
    bne p2, x12, x0, pred

    lli   x13, 1, 3
    sw    x13, x10, 0, 3
    halt
