START:
    ; per-thread id
    csrr  x3, 0                        ; x3 = TID

    ; set max thread count
    lli   x5, 32

    ; load stride and base
    lli   x6, 4
    lui   x7, 0x10                      ; base = 0x10000000

    ; if (tid < MAX_THREADS) -> compute
    slt x12, x3, x5
    bne 2, x12, x0

    ; addr = base + tid*stride
    mul   x9,  x3, x6, 2
    add   x10, x7, x9, 2

    ; Store TID + data above outside byte (ignored)
    lui   x3, 0xFF, 2
    sb    x3, 0(x10), 2
    sb    x3, 1(x10), 2
    sb    x3, 2(x10), 2
    sb    x3, 3(x10), 2

    halt
