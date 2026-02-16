START:
    ; per-thread id
    csrr  x3, x0                        ; x3 = TID

    ; set max thread count
    lli   x5, 32                        ; MAX_THREADS = 32

    ; load stride and base
    lli   x6, 4                         ; stride = 4 bytes/thread
    lui   x7, 0x10                      ; heap base address = 0x10000000

    ; if (tid < MAX_THREADS) -> compute
    blt   p2, x3, x5, pred

    ; -----------------------------
    ; Test 1: slti with +16
    ; y_pos = (TID < 16) ? 1 : 0
    ; -----------------------------
    slti  x8, x3, 16, 2                 ; x8 = (x3 < 16)

    ; addr_pos = base + tid*stride
    mul   x9,  x3, x6, 2                ; x9  = TID * 4
    add   x10, x7, x9, 2                ; x10 = base + offset

    ; store y_pos
    sw    x8, x10, 0, 2

    ; -----------------------------
    ; Test 2: slti with negative imm (-8)
    ; rs1 = TID - 16   -> range [-16..15]
    ; y_neg = (rs1 < -8) ? 1 : 0
    ; -----------------------------
    addi  x11, x3, -16, 2               ; x11 = TID - 16
    slti  x12, x11, -8, 2               ; x12 = (x11 < -8)

    ; addr_neg = (base + 0x100) + tid*stride
    lli   x13, 0x100, 2
    add   x14, x7, x13, 2               ; x14 = base + 0x100
    add   x15, x14, x9, 2               ; x15 = (base+0x100) + offset

    ; store y_neg
    sw    x12, x15, 0, 2

    halt
