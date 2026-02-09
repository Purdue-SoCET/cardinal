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

    ; rs1 = 0x80000000 | TID
    lui   x8, 0x80, 2
    or    x8, x8, x3, 2

    ; rs2 = 0x80000010
    lui   x11, 0x80, 2
    ori   x11, x11, 0x10, 2

    ; if (rs1 >=u rs2) store 1
    bgeu  TAKEN, x8, x11, 2

    halt

TAKEN:
    lli   x12, 1, 2
    sw    x12, x10, 0, 2
    halt
