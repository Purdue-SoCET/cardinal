START:
    ; Get thread ID
    csrr x3, x0 #fictional thread ID
    
    ; load arguments from 0x20 - TODO: Update from CSRR arg pointer
    lui x15, 0x20
    lw x4, x15, 0               ; x4 = N = Width of array
    lw x5, x15, 4               ; x5 = A = Scalar
    lw x6, x15, 8               ; x6 = X = Array 1 start
    lw x7, x15, 12              ; x7 = Y = Array 1 start

    ; if (i < N)
    blt p2, x3, x4

    ; Add offset for X and Y
    slli x3, x3, 2
    add x6, x6, x3, 2
    add x7, x7, x3, 2

    ; load x[i] and y[i]
    lw x8, x6, 0, 2             ; x8 = x[i]
    lw x9, x7, 0, 2             ; x9 = y[i]

    ; x10 = a * x[i]
    mulf x10, x8, x5, 2
    ; x11 = x10 + y[i]
    addf x11, x10, x9, 2
    ; y[i] = x11
    sw x11, x7, 0, 2
   
    halt