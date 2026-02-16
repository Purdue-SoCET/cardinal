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

    ; addr = base + tid*stride   (reused by both tests)
    mul   x9,  x3, x6, 2                ; x9  = TID * 4
    add   x10, x7, x9, 2                ; x10 = base + offset

    ; -----------------------------
    ; Test 1: slli by 1
    ; y1 = 1 << 1 = 0x00000002
    ; -----------------------------
    lli   x8, 1, 2                      ; x8 = 1
    slli  x8, x8, 1, 2                  ; x8 = x8 << 1
    sw    x8, x10, 0, 2                 ; store y1

    ; -----------------------------
    ; Test 2: slli by 31
    ; y2 = 1 << 31 = 0x80000000
    ; -----------------------------
    lli   x11, 1, 2                     ; x11 = 1
    slli  x11, x11, 31, 2               ; x11 = x11 << 31

    ; addr2 = (base + 0x100) + tid*stride
    lli   x12, 0x100, 2
    add   x13, x7, x12, 2               ; x13 = base + 0x100
    add   x14, x13, x9, 2               ; x14 = (base+0x100) + offset
    sw    x11, x14, 0, 2                ; store y2

    halt
