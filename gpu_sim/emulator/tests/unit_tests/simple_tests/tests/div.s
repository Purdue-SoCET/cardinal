START:
    ; per-thread id
    csrr  x3, x1000                     ; x3 = TID

    ; set max thread count
    lli   x5, 32                        ; MAX_THREADS = 32

    ; load stride and base
    lli   x6, 4                         ; stride = 4 bytes/thread
    lui   x7, 0x10                      ; heap base address

    ; if (tid < MAX_THREADS) -> compute
    blt   p2, x3, x5, pred
    jal   x16, COMPUTE, pred

STOP:
    halt

COMPUTE:
    ; rs2 = 2
    lli   x9, 2                         ; x9 = 2

    ; div: rd = rs1 / rs2 (floor for positive ints)
    div   x10, x3, x9, 2                ; x10 = TID / 2

    ; address = base + tid*stride
    mul   x11, x3, x6, 2                ; x11 = TID * stride
    add   x12, x7, x11, 2               ; x12 = base + offset

    ; store result (integer)
    sw    x10, x12, 0, 2

    ; finish
    jal   x16, STOP, pred
