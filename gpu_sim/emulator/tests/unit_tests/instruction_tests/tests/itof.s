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

    ; addr = base + tid*stride  (reused)
    mul   x9,  x3, x6, 2
    add   x10, x7, x9, 2

    ; -----------------------------
    ; Test 1: itof(TID)
    ; -----------------------------
    itof  x8, x3, 2                     ; x8 = float(tid)
    sw    x8, x10, 0, 2                 ; store float bits

    ; -----------------------------
    ; Test 2: itof(TID - 16)
    ; -----------------------------
    addi  x11, x3, -16, 2               ; x11 = tid - 16
    itof  x12, x11, 2                   ; x12 = float(tid - 16)

    ; addr2 = (base + 0x100) + tid*stride
    lli   x13, 0x100, 2
    add   x14, x7, x13, 2
    add   x15, x14, x9, 2
    sw    x12, x15, 0, 2

    halt
