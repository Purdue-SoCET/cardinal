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
    ; Setup: store known word
    ; val = 0x11223344 ^ TID
    ; -----------------------------
    lui   x8, 0x11, 2                   ; x8 = 0x11000000
    lmi   x8, 0x2, 2                    ; x8 = 0x11200000
    lli   x8, 0x44, 2                   ; x8 = 0x11223344 (per your nibble loaders)
    xori  x8, x8, 0x0, 2                ; (no-op placeholder if your assembler needs 2-tagged op)
    xor   x8, x8, x3, 2                 ; x8 = 0x11223344 ^ TID
    sw    x8, x10, 0, 2                 ; store to memory

    ; -----------------------------
    ; Test: lw back
    ; -----------------------------
    lw    x11, x10, 0, 2                ; x11 = *(word*)addr

    ; store loaded result to base+0x100 region
    lli   x12, 0x100, 2
    add   x13, x7, x12, 2
    add   x14, x13, x9, 2
    sw    x11, x14, 0, 2

    halt
