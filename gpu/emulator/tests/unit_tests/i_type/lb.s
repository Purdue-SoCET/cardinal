START:
    ; per-thread id
    csrr  x3, x0                        ; x3 = TID

    ; set max thread count
    lli   x5, 32

    ; load stride and base
    lli   x6, 20
    lui   x7, 0x10                      ; base = 0x10000000

    ; if (tid < MAX_THREADS) -> compute
    blt   p2, x3, x5, pred

    ; addr = base + tid*stride
    mul   x9,  x3, x6, 2
    add   x10, x7, x9, 2

    ; -----------------------------
    ; Setup word: 0x807F01FF
    ; bytes (little-endian):
    ;   [0]=0xFF, [1]=0x01, [2]=0x7F, [3]=0x80
    ; -----------------------------
    lui   x8, 0x80, 2
    lmi   x8, 0x7, 2
    lli   x8, 0xFF, 2                   ; x8 = 0x807F01FF
    sw    x8, x10, 0, 2

    ; -----------------------------
    ; lb offset 0
    ; -----------------------------
    lb    x11, x10, 0, 2
    sw    x11, x10, 4, 2

    ; -----------------------------
    ; lb offset 1
    ; -----------------------------
    lb    x11, x10, 1, 2
    sw    x11, x10, 8, 2

    ; -----------------------------
    ; lb offset 2
    ; -----------------------------
    lb    x11, x10, 2, 2
    sw    x11, x10, 12, 2

    ; -----------------------------
    ; lb offset 3
    ; -----------------------------
    lb    x11, x10, 3, 2
    sw    x11, x10, 16, 2

    halt
