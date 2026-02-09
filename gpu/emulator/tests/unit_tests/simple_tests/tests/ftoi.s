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
    ; Test 1: ftoi(itof(TID)) -> TID
    ; -----------------------------
    itof  x8, x3, 2                     ; x8 = float(tid)
    ftoi  x11, x8, 2                    ; x11 = int(float(tid))
    sw    x11, x10, 0, 2                ; store int

    ; -----------------------------
    ; Test 2: ftoi(itof(TID - 16)) -> (TID - 16)
    ; -----------------------------
    addi  x12, x3, -16, 2               ; x12 = tid - 16
    itof  x13, x12, 2                   ; x13 = float(tid - 16)
    ftoi  x14, x13, 2                   ; x14 = int(float(tid - 16))

    ; addr2 = (base + 0x100) + tid*stride
    lli   x15, 0x100, 2
    add   x16, x7, x15, 2
    add   x17, x16, x9, 2
    sw    x14, x17, 0, 2

    halt
