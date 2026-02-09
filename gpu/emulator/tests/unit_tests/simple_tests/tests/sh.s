START:
    ; per-thread id
    csrr  x3, x0                        ; x3 = TID

    ; set max thread count
    lli   x5, 32

    ; load stride and base
    lli   x6, 4
    lui   x7, 0x10                      ; base = 0x10000000

    ; if (tid < MAX_THREADS) -> compute
    blt   p2, x3, x5, pred

    ; addr = base + tid*stride
    mul   x9,  x3, x6, 2
    add   x10, x7, x9, 2

    ; -----------------------------
    ; Setup: store 0xFFFFFFFF
    ; -----------------------------
    ori   x8, x0, -1, 2                 ; x8 = 0xFFFFFFFF
    sw    x8, x10, 0, 2

    ; -----------------------------
    ; Test 1: sh low halfword at +0
    ; half = 0x5500 | TID  (keeps it in low 16b)
    ; -----------------------------
    sll   x11, x3, x6, 2                ; x11 = TID << 4
    sll   x11, x11, x6, 2               ; x11 = TID << 8
    ori   x11, x11, 0x55, 2             ; x11 = (TID<<8) | 0x55   (<= 0x1F55)

    sh    x11, x10, 0, 2                ; store to low half
    lw    x12, x10, 0, 2                ; read full word back

    ; store readback to base+0x100
    lli   x13, 0x100, 2
    add   x14, x7, x13, 2
    add   x15, x14, x9, 2
    sw    x12, x15, 0, 2

    ; -----------------------------
    ; Test 2: sh high halfword at +2
    ; half = 0xAA00 | TID
    ; -----------------------------
    sll   x11, x3, x6, 2                ; x11 = TID << 4
    sll   x11, x11, x6, 2               ; x11 = TID << 8
    ori   x11, x11, 0xAA, 2             ; x11 = (TID<<8) | 0xAA   (<= 0x1FAA)

    sh    x11, x10, 2, 2                ; store to high half
    lw    x12, x10, 0, 2                ; read full word back

    ; store readback to base+0x200
    lli   x13, 0x200, 2
    add   x14, x7, x13, 2
    add   x15, x14, x9, 2
    sw    x12, x15, 0, 2

    halt
