    lli   r1, 0x15                   # r1 = 21 seed for all I-type ops
    addi  r10, r1, 7                 # r10 = 21 + 7
    subi  r11, r1, 5                 # r11 = 21 - 5   (two's-comp immediate)
    andi  r12, r1, 0x0F              # r12 = 0x15 & 0x0F -> 0x05
    ori   r13, r1, 0x20              # r13 = 0x15 | 0x20 -> 0x35
    xori  r14, r1, 0xFF              # r14 = 0x15 ^ 0xFF (flip low byte)
    slti  r15, r1, 32                # r15 = (21 < 32) ? 1 : 0 (signed)
    sltiu r16, r1, 16                # r16 = (21 < 16) ? 1 : 0 (unsigned)
    slli  r17, r1, 2                 # r17 = 21 << 2
    srli  r18, r1, 1                 # r18 = 21 >> 1 (logical)
    srai  r19, r1, 1                 # r19 = 21 >> 1 (arithmetic)
    halt                              # end








