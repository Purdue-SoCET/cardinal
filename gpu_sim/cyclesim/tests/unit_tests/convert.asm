    lli   r1, 7                     # positive integer seed 7
    lli   r2, -4                    # negative integer seed -4 (two's complement)

    lli   r3, 0x0000                # low for +2.5f = 0x40200000
    lmi   r3, 0x200                 # mid for +2.5f
    lui   r3, 0x40                  # high for +2.5f

    lli   r4, 0x0000                # low for -3.5f = 0xC0600000
    lmi   r4, 0x600                 # mid for -3.5f
    lui   r4, 0xC0                  # high for -3.5f

    itof  r10, r1                   # 7 → 7.0f
    itof  r11, r2                   # -4 → -4.0f
    ftoi  r12, r3                   # +2.5f → 2
    ftoi  r13, r4                   # -3.5f → -3
    
    halt                            # end