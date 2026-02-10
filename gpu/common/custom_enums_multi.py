from aenum import MultiValueEnum
from enum import Enum
from bitstring import Bits

# ISA Teal Card v2 (used for Enum declarations): https://docs.google.com/spreadsheets/d/1quvfY0Q_mLP5VfUaNGiiruGoqjCMpCyCKM9KlqbujYM/edit?usp=sharing

# Instruction Type Enum (first 4 MSBs of 7-bit opcode)
class Instr_Type(MultiValueEnum):
    R_TYPE = Bits(bin='0000', length=4), Bits(bin='0001', length=4)  # 0000, 0001
    I_TYPE = Bits(bin='0010', length=4), Bits(bin='0011', length=4), Bits(bin='0100', length=4)  # 0010, 0011, 0100
    F_TYPE = Bits(bin='0101', length=4)    # 0101 (FP/conversion operations)
    S_TYPE = Bits(bin='0110', length=4), Bits(bin='0111', length=4)  # 0110, 0111
    B_TYPE = Bits(bin='1000', length=4), Bits(bin='1001', length=4)  # 1000, 1001
    U_TYPE = Bits(bin='1010', length=4)    # 1010
    C_TYPE = Bits(bin='1011', length=4)    # 1011
    J_TYPE = Bits(bin='1100', length=4)    # 1100
    P_TYPE = Bits(bin='1101', length=4)    # 1101
    H_TYPE = Bits(bin='1111', length=4)    # 1111 (Halt)

class Op(Enum):
    pass 

# R-Type Operations (opcode: 0000xxx and 0001xxx)
class R_Op(Enum):
    # From R_Op_0 (0000xxx)
    ADD = Bits(bin='0000000', length=7)   # 0000 000
    SUB = Bits(bin='0000001', length=7)   # 0000 001
    MUL = Bits(bin='0000010', length=7)   # 0000 010
    DIV = Bits(bin='0000011', length=7)   # 0000 011
    AND = Bits(bin='0000100', length=7)   # 0000 100
    OR = Bits(bin='0000101', length=7)    # 0000 101
    XOR = Bits(bin='0000110', length=7)   # 0000 110
    SLT = Bits(bin='0000111', length=7)   # 0000 111
    # From R_Op_1 (0001xxx)
    SLTU = Bits(bin='0001000', length=7)  # 0001 000
    ADDF = Bits(bin='0001001', length=7)  # 0001 001
    SUBF = Bits(bin='0001010', length=7)  # 0001 010
    MULF = Bits(bin='0001011', length=7)  # 0001 011
    DIVF = Bits(bin='0001100', length=7)  # 0001 100
    SLL = Bits(bin='0001101', length=7)   # 0001 101
    SRL = Bits(bin='0001110', length=7)   # 0001 110
    SRA = Bits(bin='0001111', length=7)   # 0001 111
    #From R_Op_2 (1001xxx)
    SLTF = Bits(bin='1001011', length=7)
    SGE = Bits(bin='1001101', length=7)
    SGEU = Bits(bin='1001110', length=7)
    SGEF = Bits(bin='1001111', length=7)

# I-Type Operations (opcode: 0010xxx, 0011xxx, 0100xxx)
class I_Op(Enum):
    # From I_Op_0 (0010xxx)
    ADDI = Bits(bin='0010000', length=7)   # 0010 000
    XORI = Bits(bin='0010100', length=7)   # 0010 001
    ORI = Bits(bin='0010101', length=7)    # 0010 101
    SLTI = Bits(bin='0010111', length=7)   # 0010 111
    # From I_Op_1 (0011xxx)
    SLTIU = Bits(bin='0011000', length=7)  # 0011 000
    SlLI = Bits(bin='0011101', length=7)   # 0011 110
    SRAI = Bits(bin='0011111', length=7)   # 0011 111
    # From I_Op_2 (0100xxx)
    LW = Bits(bin='0100000', length=7)     # 0100 000
    LH = Bits(bin='0100001', length=7)     # 0100 001
    LB = Bits(bin='0100010', length=7)     # 0100 010
    JALR = Bits(bin='0100011', length=7)   # 0100 011

# F-Type Operations (opcode: 0101xxx) - Floating Point and Type Conversion
class F_Op(Enum):
    ISQRT = Bits(bin='0101000', length=7)  # 0101 000
    SIN = Bits(bin='0101001', length=7)    # 0101 001
    COS = Bits(bin='0101010', length=7)    # 0101 010
    ITOF = Bits(bin='0101011', length=7)   # 0101 011
    FTOI = Bits(bin='0101100', length=7)   # 0101 100

# S-Type Operations (opcode: 0110xxx, 0111xxx)
class S_Op(Enum):
    # From S_Op_0 (0110xxx)
    SW = Bits(bin='0110000', length=7)     # 0110 000
    SH = Bits(bin='0110001', length=7)     # 0110 001
    SB = Bits(bin='0110010', length=7)     # 0110 010
    # S_Op_1 (0111xxx) - Currently unused but reserved

# B-Type Operations (opcode: 1000xxx, 1001xxx)
class B_Op(Enum):
    # From B_Op_0 (1000xxx) - Predicate Write
    BEQ = Bits(bin='1000000', length=7)    # 1000 000
    BNE = Bits(bin='1000001', length=7)    # 1000 001


# U-Type Operations (opcode: 1010xxx)
class U_Op(Enum):
    AUIPC = Bits(bin='1010000', length=7)  # 1010 000
    LLI = Bits(bin='1010001', length=7)    # 1010 001
    LMI = Bits(bin='1010010', length=7)    # 1010 010
    LUI = Bits(bin='1010100', length=7)    # 1010 100

# C-Type Operations (opcode: 1011xxx)
class C_Op(Enum):
    CSRR = Bits(bin='1011000', length=7)   # 1011 000

# J-Type Operations (opcode: 1100xxx)
class J_Op(Enum):
    JAL = Bits(bin='1100000', length=7)    # 1100 000

# P-Type Operations (opcode: 1101xxx)
class P_Op(Enum):
    JPNZ = Bits(bin='1101000', length=7)   # 1101 000
    PRR = Bits(bin='1101100', length=7)
    PRW = Bits(bin='1101101', length=7)
    
# H-Type Operations (opcode: 1111xxx)
class H_Op(Enum):
    HALT = Bits(bin='1111111', length=7)   # 1111 111