START:
    ; per-thread id
    csrr  x3, x0                     ; x3 = TID

    ; set max thread count
    lli   x5, 32                        ; MAX_THREADS = 32

    ; load stride and base
    lli   x6, 4                         ; stride = 4 bytes/thread (1 word each)
    lui   x7, 0x10                      ; heap base address

    ; if (tid < MAX_THREADS) -> compute
    slt x11, x3, x5
    bne p2, x11, x0, pred

    ; address = base + tid*stride
    mul   x8, x3, x6, 2             ; TID * stride
    add   x9, x7, x8, 2             ; base + (tid*stride)

    ; Load value that would overflow when added to itself
    ; Using maximum value representable with 12-bit immediates
    ; 0xFFFFFF + 0xFFFFFF = 0x1FFFFFE
    ; In signed 32-bit arithmetic, 0xFFFFFF = 16777215 (positive)
    ; Sum = 33554430 (positive), so no overflow on this one
    ; But the framework should still record it attempted the operation
    lli   x4, 0xFFF                     ; load lower 12 bits (0xFFF)
    lui   x4, 0xFFF                     ; load upper 20 bits (makes 0xFFFFF... pattern)

    ; compute op (y = x4 + x4): tests overflow detection mechanism
    ; Even though this particular case doesn't cause overflow,
    ; the performance counter should record the ADD execution
    add   x10, x4, x4, 2

    ; store result
    sw    x10, x9, 0, 2

    ; finish
    halt
