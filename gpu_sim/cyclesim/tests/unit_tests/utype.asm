    lli   r10, 0x1234                   # load low 12 bits
    lmi   r11, 0x567                    # load middle 12 bits
    lui   r12, 0x89                     # load upper 8 bits
    auipc r13, 0                        # add upper immediate to PC (store PC+imm)
    lli   r28, buf                      # base pointer
    sw    r10, 0(r28)                   # store result of LLI
    sw    r11, 4(r28)                   # store result of LMI
    sw    r12, 8(r28)                   # store result of LUI
    sw    r13, 12(r28)                  # store result of AUIPC
    halt