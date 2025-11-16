from enum import Enum
from bitstring import Bits

# ISA Teal Card v2 (used for Enum declarations): https://docs.google.com/spreadsheets/d/1quvfY0Q_mLP5VfUaNGiiruGoqjCMpCyCKM9KlqbujYM/edit?usp=sharing

# Instruction Type Enum (first 4 MSBs of 7-bit opcode)
class Instr_Type(Enum):
    R_TYPE_0 = Bits(bin='0000', length=4)  # 0000
    R_TYPE_1 = Bits(bin='0001', length=4)  # 0001
    I_TYPE_0 = Bits(bin='0010', length=4)  # 0010
    I_TYPE_1 = Bits(bin='0011', length=4)  # 0011
    I_TYPE_2 = Bits(bin='0100', length=4)  # 0100
    F_TYPE = Bits(bin='0101', length=4)    # 0101 (FP/conversion operations)
    S_TYPE_0 = Bits(bin='0110', length=4)  # 0110
    S_TYPE_1 = Bits(bin='0111', length=4)  # 0111
    B_TYPE_0 = Bits(bin='1000', length=4)  # 1000
    B_TYPE_1 = Bits(bin='1001', length=4)  # 1001
    U_TYPE = Bits(bin='1010', length=4)    # 1010
    C_TYPE = Bits(bin='1011', length=4)    # 1011
    J_TYPE = Bits(bin='1100', length=4)    # 1100
    P_TYPE = Bits(bin='1101', length=4)    # 1101
    H_TYPE = Bits(bin='1111', length=4)    # 1111 (Halt)

class Op(Enum):
    pass

# R-Type Operations (opcode: 0000xxx and 0001xxx)
class R_Op_0(Op):
    ADD = Bits(bin='000', length=3)   # 000
    SUB = Bits(bin='001', length=3)   # 001
    MUL = Bits(bin='010', length=3)   # 010
    DIV = Bits(bin='011', length=3)   # 011
    AND = Bits(bin='100', length=3)   # 100
    OR = Bits(bin='101', length=3)    # 101
    XOR = Bits(bin='110', length=3)   # 110
    SLT = Bits(bin='111', length=3)   # 111

class R_Op_1(Op):
    SLTU = Bits(bin='000', length=3)  # 000
    ADDF = Bits(bin='001', length=3)  # 001
    SUBF = Bits(bin='010', length=3)  # 010
    MULF = Bits(bin='011', length=3)  # 011
    DIVF = Bits(bin='100', length=3)  # 100
    SLL = Bits(bin='101', length=3)   # 101
    SRL = Bits(bin='110', length=3)   # 110
    SRA = Bits(bin='111', length=3)   # 111

# I-Type Operations (opcode: 0010xxx)
class I_Op_0(Op):
    ADDI = Bits(bin='000', length=3)   # 000
    SUBI = Bits(bin='001', length=3)   # 001
    ORI = Bits(bin='101', length=3)    # 101
    SLTI = Bits(bin='111', length=3)   # 111

# I-Type Operations (opcode: 0011xxx)
class I_Op_1(Op):
    SLTIU = Bits(bin='000', length=3)  # 000
    SRLI = Bits(bin='110', length=3)   # 110
    SRAI = Bits(bin='111', length=3)   # 111

# I-Type Operations (opcode: 0100xxx)
class I_Op_2(Op):
    LW = Bits(bin='000', length=3)     # 000
    LH = Bits(bin='001', length=3)     # 001
    LB = Bits(bin='010', length=3)     # 010
    JALR = Bits(bin='011', length=3)   # 011

# F-Type Operations (opcode: 0101xxx) - Floating Point and Type Conversion
class F_Op(Op):
    ISQRT = Bits(bin='000', length=3)  # 000
    SIN = Bits(bin='001', length=3)    # 001
    COS = Bits(bin='010', length=3)    # 010
    ITOF = Bits(bin='011', length=3)   # 011
    FTOI = Bits(bin='100', length=3)   # 100

# S-Type Operations (opcode: 0110xxx)
class S_Op_0(Op):
    SW = Bits(bin='000', length=3)     # 000
    SH = Bits(bin='001', length=3)     # 001
    SB = Bits(bin='010', length=3)     # 010

# S-Type Operations (opcode: 0111xxx) - Currently unused but reserved
class S_Op_1(Op):
    pass  # No operations defined yet

# B-Type Operations (opcode: 1000xxx) - Predicate Write
class B_Op_0(Op):
    BEQ = Bits(bin='000', length=3)    # 000
    BNE = Bits(bin='001', length=3)    # 001
    BGE = Bits(bin='010', length=3)    # 010
    BGEU = Bits(bin='011', length=3)   # 011
    BLT = Bits(bin='100', length=3)    # 100
    BLTU = Bits(bin='101', length=3)   # 101

# B-Type Operations (opcode: 1001xxx) - Currently unused but reserved
class B_Op_1(Op):
    pass  # No operations defined yet

# U-Type Operations (opcode: 1010xxx)
class U_Op(Op):
    AUIPC = Bits(bin='000', length=3)  # 000
    LLI = Bits(bin='001', length=3)    # 001
    LMI = Bits(bin='010', length=3)    # 010
    LUI = Bits(bin='100', length=3)    # 100

# C-Type Operations (opcode: 1011xxx)
class C_Op(Op):
    CSRR = Bits(bin='000', length=3)   # 000
    CSRW = Bits(bin='001', length=3)   # 001

# J-Type Operations (opcode: 1100xxx)
class J_Op(Op):
    JAL = Bits(bin='000', length=3)    # 000

# P-Type Operations (opcode: 1101xxx)
class P_Op(Op):
    JPNZ = Bits(bin='000', length=3)   # 000

# H-Type Operations (opcode: 1111xxx)
class H_Op(Op):
    HALT = Bits(bin='111', length=3)   # 111