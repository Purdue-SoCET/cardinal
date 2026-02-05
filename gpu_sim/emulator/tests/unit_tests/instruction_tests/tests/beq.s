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

    ; addr = base + tid*4
    mul   x9,  x3, x6, 2
    add   x10, x7, x9, 2

    ; default = 0
    sw    x0, x10, 0, 2

    ; if (TID == 0) store 1
    beq   TAKEN, x3, x0, 2

    halt

TAKEN:
    lli   x11, 1, 2
    sw    x11, x10, 0, 2
    halt
