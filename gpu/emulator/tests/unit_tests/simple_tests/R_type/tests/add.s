START:
    ; per-thread id
    csrr  x3, x1000                     ; x3 = TID

    ; load initial values
    lli   x4, 5                         ; change this to alter b in (y = TID + b)

    ; set max thread count
    lli   x5, 32                        ; MAX_THREADS = 32

    ; load stride and base
    lli   x6, 4                         ; stride = 4 bytes/thread (1 word each)
    lli   x7, 0x10000000                ; heap base address

    ; if (tid < MAX_THREADS) -> compute
    blt   p2, x3, x5, pred              ; p2 = (x3 < x5) == (TID < MAX_THREADS)
    jal   x16, COMPUTE, pred

    STOP:
        halt

    COMPUTE:
        ; compute op (y = a + b): x7 = x4 + TID
        add   x7, x4, x3, 2

        ; address = base + tid*stride
        mul   x8, x3, x6, 2             ; TID * stride
        add   x9, x7, x8, 2             ; base + (tid*stride)

        ; store result
        sw    x7, x9, 0, 2

        ; finish
        jal x16, STOP, pred
