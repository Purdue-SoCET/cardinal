START:
    ; per-thread id
    csrr  x3, x0                        ; x3 = TID

    ; set max thread count
    lli   x5, 32                        ; MAX_THREADS = 32

    ; load stride and base
    lli   x6, 4                         ; stride = 4 bytes/thread
    lui   x7, 0x10                      ; heap base address = 0x10000000

    ; if (tid < MAX_THREADS) -> compute
    blt   p2, x3, x5, pred

    ; -----------------------------
    ; Test 1: ori with +0x0F
    ; y_pos = TID | 0x0000000F
    ; -----------------------------
    ori   x8, x3, 0x0F, 2               ; x8 = TID | 0x0F

    ; addr_pos = base + tid*stride
    mul   x9,  x3, x6, 2                ; x9  = TID * 4
    add   x10, x7, x9, 2                ; x10 = base + offset

    ; store y_pos
    sw    x8, x10, 0, 2

    ; -----------------------------
    ; Test 2: ori with -16 (0xFFFFFFF0)
    ; y_neg = TID | 0xFFFFFFF0
    ; -----------------------------
    ori   x11, x3, -16, 2               ; x11 = TID | (-16)

    ; addr_neg = (base + 0x100) + tid*stride
    lli   x12, 0x100, 2
    add   x13, x7, x12, 2               ; x13 = base + 0x100
    add   x14, x13, x9, 2               ; x14 = (base+0x100) + offset

    ; store y_neg
    sw    x11, x14, 0, 2

    halt
