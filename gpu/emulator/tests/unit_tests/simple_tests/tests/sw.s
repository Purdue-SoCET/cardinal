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
    mul   x9,  x3, x6, 2                ; x9  = TID*4
    add   x10, x7, x9, 2                ; x10 = addr
    
    lui   x3, 0xFF, 2                   ; Ensure upper bits are stored
    sw    x3, x10, 0, 2                 ; store word

    halt
