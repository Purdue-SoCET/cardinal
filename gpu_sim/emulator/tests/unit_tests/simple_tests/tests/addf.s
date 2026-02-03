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
    ; convert TID to float
    itof  x8, x3, 2                     ; x8 = float(TID)

    ; load 0.5 as IEEE-754 float
    lli   x9, 0x3F000000                ; x9 = 0.5f

    ; float add: y = float(TID) + 0.5
    addf  x10, x8, x9, 2                ; x10 = y

    ; address = base + tid*stride
    mul   x11, x3, x6, 2                ; x11 = TID * stride
    add   x12, x7, x11, 2               ; x12 = base + offset

    ; store result
    sw    x10, x12, 0, 2

    ; finish
    jal   x16, STOP, pred
