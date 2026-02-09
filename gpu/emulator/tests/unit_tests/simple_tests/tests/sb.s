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
    ; Setup: store 0x00000000
    ; -----------------------------
    sw    x0, x10, 0, 2

    ; -----------------------------
    ; sb offset 0: b0 = 0x10 | TID
    ; -----------------------------
    ori   x8, x3, 0x10, 2
    sb    x8, x10, 0, 2

    ; -----------------------------
    ; sb offset 1: b1 = 0x20 | TID
    ; -----------------------------
    ori   x8, x3, 0x20, 2
    sb    x8, x10, 1, 2

    ; -----------------------------
    ; sb offset 2: b2 = 0x40 | TID
    ; -----------------------------
    ori   x8, x3, 0x40, 2
    sb    x8, x10, 2, 2

    ; -----------------------------
    ; sb offset 3: b3 = 0x80 | TID
    ; -----------------------------
    ori   x8, x3, 0x80, 2
    sb    x8, x10, 3, 2

    ; read full word back
    lw    x11, x10, 0, 2

    ; store readback to base+0x100
    lli   x12, 0x100, 2
    add   x13, x7, x12, 2
    add   x14, x13, x9, 2
    sw    x11, x14, 0, 2

    halt
