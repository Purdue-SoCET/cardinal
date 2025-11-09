start:
    lli   r1, 0x15                 # r1 = 21 (seed A for binary ops)
    lli   r2, 0x03                 # r2 = 3  (seed B for binary ops)
    lli   r3, 0x02                 # r3 = 2  (seed for shift amount)
    add   r10, r1, r2              # r10 = 21 + 3
    sub   r11, r1, r2              # r11 = 21 - 3
    mul   r12, r1, r2              # r12 = 21 * 3
    div   r13, r1, r2              # r13 = 21 / 3 (integer trunc per spec)
    and   r14, r1, r2              # r14 = r1 & r2
    or    r15, r1, r2              # r15 = r1 | r2
    xor   r16, r1, r2              # r16 = r1 ^ r2
    slt   r17, r1, r2              # r17 = (r1 < r2) ? 1 : 0 (signed)
    sltu  r18, r1, r2              # r18 = (r1 < r2) ? 1 : 0 (unsigned)
    srl   r19, r1, r3              # r19 = r1 >> 2 (logical)
    sll   r20, r1, r3              # r20 = r1 << 2
    sra   r21, r1, r3              # r21 = r1 >> 2 (arithmetic)
    halt                            # end




