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
    ; Test 1: srli by 1
    ; y1 = 0x80000000 >> 1 = 0x40000000
    ; -----------------------------
    lui   x8, 0x80, 2                   ; x8 = 0x80000000
    srli  x8, x8, 1, 2                  ; x8 = x8 >> 1 (logical)
    sw    x8, x10, 0, 2                 ; store y1

    ; -----------------------------
    ; Test 2: srli by 31
    ; y2 = 0x80000000 >> 31 = 0x00000001
    ; -----------------------------
    lui   x11, 0x80, 2                  ; x11 = 0x80000000
    srli  x11, x11, 31, 2               ; x11 = x11 >> 31 (logical)

    ; addr2 = (base + 0x100) + tid*stride
    lli   x12, 0x100, 2
    add   x13, x7, x12, 2               ; x13 = base + 0x100
    add   x14, x13, x9, 2               ; x14 = (base+0x100) + offset
    sw    x11, x14, 0, 2                ; store y2

    halt
