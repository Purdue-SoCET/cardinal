START:
    ; per-thread id
    csrr  x3, x0                     ; x3 = TID

    ; load initial values
    lli   x4, 0                         ; change this to alter b in (y = b + TID)

    ; set max thread count
    lli   x5, 33                        ; MAX_THREADS = 33

    ; load stride and base
    lli   x6, 4                         ; stride = 4 bytes/thread (1 word each)
    lui   x7, 0x10                      ; heap base address

    ; if (tid < MAX_THREADS) -> compute
    blt   p2, x3, x5, pred              ; p2 = (x3 < x5) == (TID < MAX_THREADS)

    ; address = base + tid*stride
    mul   x8, x3, x6, 2             ; TID * stride
    add   x9, x7, x8, 2             ; base + (tid*stride)


    ; Get new predicate mask for P2 from 0x20000000
    lui   x10, 0x20, 2
    prlw  p3, x10, 0

    ; Store 1 for only predicated instructions
    lli   x11, 1, 3
    sw    x11, x9, 0, 3

    halt