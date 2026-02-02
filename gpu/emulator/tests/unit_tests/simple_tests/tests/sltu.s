START:
    ; per-thread id
    csrr  x3, x1000                     ; x3 = TID

    ; set max thread count
    lli   x5, 32                        ; MAX_THREADS = 32

    ; load stride and base
    lli   x6, 4                         ; stride = 4 bytes/thread
    lli   x7, 0x10                      ; heap base address

    ; if (tid < MAX_THREADS) -> compute
    blt   p2, x3, x5, pred
    jal   x16, COMPUTE, pred

STOP:
    halt

COMPUTE:
    ; b = 0x80000000 (unsigned large, signed negative)
    lui   x9, 0x80, 2                   ; x9 = b

    ; sltu (unsigned): result = (a < b) ? 1 : 0
    ; expected: TRUE for all TID 0..31
    sltu  x10, x3, x9, 2                ; x10 = (a < b) unsigned

    ; address = base + tid*stride
    mul   x11, x3, x6, 2                ; TID * stride
    add   x12, x7, x11, 2               ; base + offset

    ; store result
    sw    x10, x12, 0, 2

    ; finish
    jal   x16, STOP, pred
