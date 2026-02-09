START:
    ; per-thread id
    csrr  x3, x0                        ; x3 = TID

    ; set max thread count
    lli   x5, 32                        ; MAX_THREADS = 32

    ; load stride and base
    lli   x6, 4                         ; stride = 4 bytes/thread
    lui   x7, 0x10                      ; base = 0x10000000

    ; if (tid < MAX_THREADS) -> compute
    blt   p2, x3, x5, pred

    ; addr = base + tid*stride
    mul   x9,  x3, x6, 2                ; x9  = TID*4
    add   x10, x7, x9, 2                ; x10 = addr

    ; -----------------------------
    ; sw: store per-thread word
    ; val = (TID << 8) | 0xA5
    ; -----------------------------
    sll   x8, x3, x6, 2                 ; x8 = TID << 4  (since x6=4)
    sll   x8, x8, x6, 2                 ; x8 = TID << 8
    ori   x8, x8, 0xA5, 2               ; x8 = (TID<<8) | 0xA5

    sw    x8, x10, 0, 2                 ; store word
    lw    x11, x10, 0, 2                ; read back

    ; store readback to base+0x100
    lli   x12, 0x100, 2
    add   x13, x7, x12, 2
    add   x14, x13, x9, 2
    sw    x11, x14, 0, 2

    halt
