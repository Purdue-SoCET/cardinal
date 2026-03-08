START:
    ; per-thread id
    csrr  x3, x0                        ; x3 = TID (Integer)

    ; set max thread count
    lli   x5, 32                        ; MAX_THREADS = 32

    ; load stride and base
    lli   x6, 4                         ; stride = 4 bytes/thread
    lui   x7, 0x10                      ; heap base address

    ; if (tid < MAX_THREADS) -> compute
    blt   p2, x3, x5, pred              ; p2 = (TID < MAX_THREADS)

    ; x9 = itof(x3)
    itof x9, x3, 2                   ; x9 = (float)TID

    ; x10 = 15.5
    lli   x10, 0x000, 2
    lmi   x10, 0x780, 2
    lui   x10, 0x41, 2

    ; TIDs 0-15  < 15.5  => Result 1
    ; TIDs 16-31 > 15.5  => Result 0
    sltf  x11, x9, x10, 2               ; x11 = (x9 < x10) float

    ; address = base + tid*stride
    mul   x12, x3, x6, 2                ; x12 = TID * stride
    add   x13, x7, x12, 2               ; x13 = base + offset

    ; store result
    sw    x11, x13, 0, 2

    halt