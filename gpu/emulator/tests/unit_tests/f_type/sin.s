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

    ; rs1 = float(TID)
    itof  x8, x3, 2                     ; x8 = float(tid)

    ; rd = sin(rs1)
    sin   x9, x8, 2                     ; x9 = sin(float(tid))  (float bits)

    ; addr = base + tid*stride
    mul   x10, x3, x6, 2
    add   x11, x7, x10, 2

    ; store result
    sw    x9, x11, 0, 2

    halt
