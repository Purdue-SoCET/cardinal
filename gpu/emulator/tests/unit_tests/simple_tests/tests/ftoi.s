START:
    ; per-thread id
    csrr  x3, x0                        ; x3 = TID

    ; set max thread count
    lli   x5, 32

    ; load stride and base
    lli   x6, 8
    lui   x7, 0x10                      ; base = 0x10000000

    ; if (tid < MAX_THREADS) -> compute
    blt   p2, x3, x5, pred

    ; addr = base + tid*stride  (reused)
    mul   x9,  x3, x6, 2
    add   x10, x7, x9, 2

    ; -----------------------------
    ; Test 1: ftoi(4.56) -> 4
    ; -----------------------------
    lui   x8, 0x40, 2
    lmi   x8, 0x91E, 2
    lli   x8, 0xB85, 2
    ftoi  x11, x8, 2                    ; x11 = int(float(tid))
    sw    x11, x10, 0, 2                ; store int

    ; -----------------------------
    ; Test 1: ftoi(-4.56) -> -4
    ; -----------------------------
    lui   x8, 0xC0, 2
    lmi   x8, 0x91E, 2
    lli   x8, 0xB85, 2
    ftoi  x11, x8, 2                    ; x11 = int(float(tid))
    sw    x11, x10, 4, 2                ; store int

    halt
