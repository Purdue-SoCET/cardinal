START:
    ; per-thread id
    csrr  x3, x0                        ; x3 = TID

    ; set max thread count
    lli   x5, 1                         ; MAX_THREADS = 1

    ; load stride and base
    lli   x6, 4                         ; stride = 4 bytes/thread
    lui   x7, 0x10                      ; heap base address

    ; if (tid < MAX_THREADS) -> compute
    blt   p2, x3, x5, pred

    ; address = base + tid*stride
    mul   x8, x3, x6                    ; TID * stride
    add   x9, x7, x8                    ; base + (tid*stride)

    jpnz  p2, WARP_0

WARP_1: 
    ; 2nd warp should jump here - all active
    ; All store 1
    lli x10, 2
    sw x10, x9, 0
    halt

WARP_0:
    ; 1st warp should jump here
    lli x10, 1
    sw x10, x9, 0
    halt
