START:
    ; per-thread id
    csrr  x3, x0                        ; x3 = TID

    ; set max thread count
    lli   x5, 32                        ; MAX_THREADS = 32

    ; load stride and base
    lli   x6, 4                         ; stride = 4 bytes/thread
    lui   x7, 0x10                      ; base = 0x10000000

    ; if (tid < MAX_THREADS) -> enable PR2
    blt   p2, x3, x5, pred

    ; addr = base + tid*stride
    mul   x9,  x3, x6, 2
    add   x10, x7, x9, 2

    ; -----------------------------
    ; Marker BEFORE jump: 0x11111111
    ; -----------------------------
    lui   x8, 0x11, 2
    lmi   x8, 0x1,  2
    lli   x8, 0x11, 2                   ; x8 = 0x11111111
    sw    x8, x10, 0, 2

    ; -----------------------------
    ; jal: jump to TARGET, write link into x16
    ; -----------------------------
    jal   x16, TARGET, 2

    ; If jal is not executed (inactive threads), fall through here
    halt

TARGET:
    ; recompute addr = base + tid*stride (safe)
    mul   x9,  x3, x6, 2
    add   x10, x7, x9, 2

    ; Marker AFTER jump: 0x22222222  -> store to base + 0x100
    lui   x8, 0x22, 2
    lmi   x8, 0x2,  2
    lli   x8, 0x22, 2                   ; x8 = 0x22222222

    lli   x12, 0x100, 2
    add   x13, x7, x12, 2
    add   x14, x13, x9,  2
    sw    x8,  x14, 0,  2

    ; Store link register x16 -> base + 0x200
    lli   x12, 0x200, 2
    add   x13, x7, x12, 2
    add   x14, x13, x9,  2
    sw    x16, x14, 0,  2

    halt
