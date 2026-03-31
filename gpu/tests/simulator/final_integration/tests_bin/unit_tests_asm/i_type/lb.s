START:
    ; per-thread id
    csrr  x3, 0                        ; x3 = TID

    ; set max thread count
    lli   x5, 32

    ; load stride and base
    lli   x6, 20
    lui   x7, 0x10                      ; base = 0x10000000

    ; if (tid < MAX_THREADS) -> compute
    slt x12, x3, x5
    bne 2, x12, x0

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
    sw    x8, 0(x10), 2

    ; -----------------------------
    ; lb offset 0
    ; -----------------------------
    lb    x11, 0(x10), 2
    sw    x11, 4(x10), 2

    ; -----------------------------
    ; lb offset 1
    ; -----------------------------
    lb    x11, 1(x10), 2
    sw    x11, 8(x10), 2

    ; -----------------------------
    ; lb offset 2
    ; -----------------------------
    lb    x11, 2(x10), 2
    sw    x11, 12(x10), 2

    ; -----------------------------
    ; lb offset 3
    ; -----------------------------
    lb    x11, 3(x10), 2
    sw    x11, 16(x10), 2

    halt
