#code for I
csrr x3, x1000 #fictional thread ID
## load arguments, default values ok
lli x15, 92
lw x4, x15, 0  #n
lli x15, 96
lw x5, x15, 0 #a
lli x15, 100
lw x6, x15, 0 #x array start
lli x15, 100
lmi x15, 1
lw x7, x15, 0 #y array start
## if (i < n)
blt p2, x3, x4, pred, 1, 1 #compute predicate 
jal x16, COMPUTE_LABEL, pred, 1, 1 #jump based on predicate
DONE_LABEL:
    halt
## complete multiply
COMPUTE_LABEL:
    #compute offset for x and y
    addi x14, x0, 2
    sll x3, x3, x14
    add x8, x6, x3, 2, 1, 0
    add x9, x7, x3, 2, 0, 1
    #load current x[i] and y[i]
    lw x10, x8,0, 2, 1, 0
    lw x11, x9,0, 2, 0, 1
    # a * x[i]
    mulf x12, x10, x5, 2, 0, 1
    # + y[i]
    addf x13, x12, x11, 2, 1, 1
    #y[i] = 
    sw x13, x9,0, 2, 1, 1
    #end program
    jal x16, DONE_LABEL, pred, 1, 1