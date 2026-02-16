START:
    ; per-thread id
    csrr  x3, x0                        ; x3 = TID

    ; set max thread count
    lli   x5, 32                        ; MAX_THREADS = 32

    ; load stride and base
    lli   x6, 8                         ; stride = 4 bytes/thread
    lui   x7, 0x10                      ; base = 0x10000000

    ; if (tid < MAX_THREADS) -> enable PR2
    blt   p2, x3, x5, pred

    ; addr = base + tid*stride
    mul   x9,  x3, x6, 2
    add   x10, x7, x9, 2

    ; -----------------------------
    ; jal: jump to TARGET, write link into x16
    ; -----------------------------
    jal   x16, TARGET, 2

    ; If jal is not executed (inactive threads), fall through here
    halt

TARGET:

    ; Store 1 to indicate success
    lli   x8, 1, 2
    sw    x8,  x10, 0,  2

    ; Store link register x16
    sw    x16, x10, 4,  2

    halt
