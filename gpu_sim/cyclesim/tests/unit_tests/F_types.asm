    lli   r10, 0x0000               # r10 = 0x40800000 low12 for 4.0f
    lmi   r10, 0x800                # r10 = 0x40800000 mid12 for 4.0f
    lui   r10, 0x40                 # r10 = 0x40800000 (4.0f)
    isqrt r20, r10                  # r20 = 1 / sqrt(4.0f) → 0.5f

    lli   r11, 0x0000               # r11 = 0x00000000 low/mid for 0.0f
    lmi   r11, 0x000                # r11 = 0x00000000 mid12 for 0.0f
    lui   r11, 0x00                 # r11 = 0x00000000 (0.0f)
    sin   r21, r11                  # r21 = sin(0.0f) → 0.0f

    lli   r12, 0x0000               # r12 = 0x00000000 low/mid for 0.0f
    lmi   r12, 0x000                # r12 = 0x00000000 mid12 for 0.0f
    lui   r12, 0x00                 # r12 = 0x00000000 (0.0f)
    cos   r22, r12                  # r22 = cos(0.0f) → 1.0f

    halt                            # end