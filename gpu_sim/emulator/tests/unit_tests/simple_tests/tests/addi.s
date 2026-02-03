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
    ; -----------------------------
    ; Test 1: addi with +5
    ; y_pos = TID + 5
    ; -----------------------------
    addi  x8, x3, 5, 2                  ; x8 = TID + 5

    ; addr_pos = base + tid*stride
    mul   x9,  x3, x6, 2                ; x9  = TID * 4
    add   x10, x7, x9, 2                ; x10 = base + offset

    ; store y_pos
    sw    x8, x10, 0, 2

    ; -----------------------------
    ; Test 2: addi with -7
    ; y_neg = TID - 7
    ; -----------------------------
    addi  x11, x3, -7, 2                ; x11 = TID - 7  (negative immediate)

    ; addr_neg = (base + 0x100) + tid*stride
    lli   x12, 0x100                    ; region offset
    add   x13, x7, x12, 2               ; x13 = base + 0x100
    add   x14, x13, x9, 2               ; x14 = (base+0x100) + offset

    ; store y_neg
    sw    x11, x14, 0, 2

    ; finish
    jal   x16, STOP, pred
