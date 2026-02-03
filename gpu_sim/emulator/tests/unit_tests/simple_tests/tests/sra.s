START:
    ; per-thread id
    csrr  x3, x1000                     ; x3 = TID

    ; set max thread count
    lli   x5, 32                        ; MAX_THREADS = 32

    ; load stride and base
    lli   x6, 4                         ; stride = 4 bytes/thread
    lui   x7, 0x10                      ; heap base address

    ; if (tid < MAX_THREADS) -> compute
    blt   p2, x3, x5, pred
    jal   x16, COMPUTE, pred

STOP:
    halt

COMPUTE:
    ; rs1 = 0x80000000 (negative if interpreted as signed)
    lli   x8, 0x80000000, 2             ; x8 = value to shift

    ; sra: y = 0x80000000 >> TID (arithmetic, sign-extended)
    sra   x10, x8, x3, 2                ; x10 = result

    ; address = base + tid*stride
    mul   x11, x3, x6, 2                ; x11 = TID * stride
    add   x12, x7, x11, 2               ; x12 = base + offset

    ; store result
    sw    x10, x12, 0, 2

    ; finish
    jal   x16, STOP, pred
