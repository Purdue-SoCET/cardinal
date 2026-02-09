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

    ; rs1 = TID - 16 (signed range -16..15)
    addi  x8, x3, -16, 2

    ; if (rs1 >= 0) store 1  (signed compare)
    bge   TAKEN, x8, x0, 2

    halt

TAKEN:
    lli   x11, 1, 2
    sw    x11, x10, 0, 2
    halt
