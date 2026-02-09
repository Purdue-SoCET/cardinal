START:
    ; per-thread id
    csrr   x3, x0                       ; x3 = TID

    ; set max thread count
    lli    x5, 32                       ; MAX_THREADS = 32

    ; load stride and base
    lli    x6, 4                        ; stride = 4 bytes/thread
    lui    x7, 0x10                     ; base = 0x10000000

    ; if (tid < MAX_THREADS) -> enable PR2
    blt    p2, x3, x5, pred

    ; addr = base + tid*stride
    mul    x9,  x3, x6, 2
    add    x10, x7, x9, 2

    ; -----------------------------
    ; Test 1: auipc at point A
    ; rd = PC + (imm << 12)
    ; -----------------------------
    auipc  x8,  0x1, 2                  ; x8 = PC_A + 0x1000
    sw     x8,  x10, 0, 2               ; store auipc_A

    ; -----------------------------
    ; Test 2: auipc at point B (later PC)
    ; -----------------------------
    auipc  x11, 0x1, 2                  ; x11 = PC_B + 0x1000

    ; store auipc_B to base + 0x100
    lli    x12, 0x100, 2
    add    x13, x7, x12, 2
    add    x14, x13, x9, 2
    sw     x11, x14, 0, 2

    halt
