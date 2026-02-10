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

    lmi   x3, 0x101                     ; x3 = 0x101TID ... expect MSB to be cut off, with "1TID" stored
    sh    x11, x10, 0, 2                ; store to low half
    sh    x11, x10, 2, 2                ; store to high half

    halt
