def encode_instruction(opcode, rd=1, rs1=2, rs2=3, pred=0, start=1, end=1):
    """Encodes a 32-bit instruction from given fields according to the GPU ISA format."""
    inst = ((end & 1) << 31) | ((start & 1) << 30) | \
           ((pred & 0x1F) << 25) | ((rs2 & 0x3F) << 19) | \
           ((rs1 & 0x3F) << 13) | ((rd & 0x3F) << 7) | \
           (opcode & 0x7F)
    return f"0x{inst:08X}"

ISA_PACKETS = {
    "add":  encode_instruction(0b0000000),
    "sub":  encode_instruction(0b0000001),
    "mul":  encode_instruction(0b0000010),
    "div":  encode_instruction(0b0000011),
    "lw":   encode_instruction(0b0100000),
    "sw":   encode_instruction(0b0110000),
    "beq":  encode_instruction(0b1000000),
    "bne":  encode_instruction(0b1000001),
    "bge":  encode_instruction(0b1000010),
    "bgeu": encode_instruction(0b1000011),
    "blt":  encode_instruction(0b1000100),
    "bltu": encode_instruction(0b1000101),
    "jal":  encode_instruction(0b1100000),
    "halt": encode_instruction(0b1111111),
}
