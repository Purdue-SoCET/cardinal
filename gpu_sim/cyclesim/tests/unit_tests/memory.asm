    lli   r28, buf                      # r28 = base pointer
    lli   r1, 0xC3D4                    # lower bits of 0xA1B2C3D4
    lmi   r1, 0xB2                      # middle bits = 0xB2
    lui   r1, 0xA1                      # upper bits = 0xA1 → full 0xA1B2C3D4
    sw    r1, 0(r28)                    # store full word at buf+0
    lli   r2, 0x0E0F                    # 16-bit half pattern
    sh    r2, 4(r28)                    # store half at buf+4
    lli   r3, 0x7A                      # 8-bit byte pattern
    sb    r3, 6(r28)                    # store byte at buf+6
    lw    r10, 0(r28)                   # load word into r10
    lh    r11, 4(r28)                   # load half into r11
    lb    r12, 6(r28)                   # load byte into r12
    sw    r11, 8(r28)                   # store LH result as word
    sw    r12, 12(r28)                  # store LB result as word
    sh    r10, 16(r28)                  # store LW result as half (truncated)
    sb    r10, 18(r28)                  # store LW result as byte (truncated)
    sh    r12, 20(r28)                  # store LB result as half
    sb    r11, 22(r28)                  # store LH result as byte
    sw    r10, 24(r28)                  # write back LW result for dump
    sh    r11, 28(r28)                  # write back LH result for dump
    sb    r12, 30(r28)                  # write back LB result for dump

    halt                                # end
