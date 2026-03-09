START:
    ; per-thread id
    csrr  x3, x0                        ; x3 = TID

    ; set max thread count
    lli   x5, 32                        ; MAX_THREADS = 32

    ; load stride and base
    lli   x6, 4                         ; stride = 4 bytes/thread (1 word each)
    lui   x7, 0x10                      ; heap base address

    ; if (tid < MAX_THREADS) -> compute
    blt   p2, x3, x5, pred              ; p2 = (TID < MAX_THREADS)

    ; build a signed value: a = TID - 16
    ; use two's complement for -16: 0xFFFFFFF0
    lli   x8, 0xFF0, 2                  ; x8 = -16
    lmi   x8, 0xFFF, 2
    lui   x8, 0xFF, 2
    add   x9, x3, x8, 2                 ; x9 = a = TID - 16

    ; b = 0
    lli   x10, 0, 2                     ; x10 = b = 0

    ; slt (signed): result = (a < b) ? 1 : 0
    ; expected: TID 0..15 => (TID-16) is negative  => 1
    ;           TID 16..31 => (TID-16) is >= 0     => 0
    slt   x11, x9, x10, 2               ; x11 = (x9 < x10) signed

    ; address = base + tid*stride
    mul   x12, x3, x6, 2                ; x12 = TID * stride
    add   x13, x7, x12, 2               ; x13 = base + (TID*stride)

    ; store result (one word per thread)
    sw    x11, x13, 0, 2

    halt
