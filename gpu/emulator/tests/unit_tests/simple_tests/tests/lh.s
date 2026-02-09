START:
    ; per-thread id
    csrr  x3, x0                        ; x3 = TID

    ; set max thread count
    lli   x5, 32                        ; MAX_THREADS = 32

    ; load stride and base
    lli   x6, 4
    lui   x7, 0x10                      ; base = 0x10000000

    ; if (tid < MAX_THREADS) -> compute
    blt   p2, x3, x5, pred

    ; addr = base + tid*stride
    mul   x9,  x3, x6, 2
    add   x10, x7, x9, 2

    ; -----------------------------
    ; Setup word: 0x80017FFF
    ;  - low half = 0x7FFF (positive)
    ;  - high half = 0x8001 (negative if sign-extended by lh)
    ; -----------------------------
    lui   x8, 0x80, 2
    lmi   x8, 0x1, 2
    lli   x8, 0xFF, 2                   ; x8 = 0x80017FFF (per your nibble loaders)
    sw    x8, x10, 0, 2

    ; -----------------------------
    ; Test 1: lh low halfword (offset 0)
    ; -----------------------------
    lh    x11, x10, 0, 2

    lli   x12, 0x100, 2
    add   x13, x7, x12, 2
    add   x14, x13, x9, 2
    sw    x11, x14, 0, 2

    ; -----------------------------
    ; Test 2: lh high halfword (offset 2)
    ; -----------------------------
    lh    x15, x10, 2, 2

    lli   x12, 0x200, 2
    add   x13, x7, x12, 2
    add   x14, x13, x9, 2
    sw    x15, x14, 0, 2

    halt
