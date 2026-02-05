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
    mul   x9,  x3, x6, 2
    add   x10, x7, x9, 2

    ; -----------------------------
    ; Test 1: srai by 1
    ; y1 = 0x80000000 >> 1 (arith)
    ; -----------------------------
    lui   x8, 0x80, 2                   ; x8 = 0x80000000
    srai  x8, x8, 1, 2                  ; x8 = x8 >> 1 (arith)
    sw    x8, x10, 0, 2                 ; store y1

    ; -----------------------------
    ; Test 2: srai by 31
    ; y2 = 0x80000000 >> 31 (arith)
    ; -----------------------------
    lui   x11, 0x80, 2                  ; x11 = 0x80000000
    srai  x11, x11, 31, 2               ; x11 = x11 >> 31 (arith)

    ; addr2 = (base + 0x100) + tid*stride
    lli   x12, 0x100, 2
    add   x13, x7, x12, 2
    add   x14, x13, x9, 2
    sw    x11, x14, 0, 2                ; store y2

    halt
