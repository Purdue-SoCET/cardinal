from aenum import MultiValueEnum
from enum import Enum
from bitstring import Bits

# Simplified playground ISA
# Keeps the same overall structure as the full ISA:
#   - Instr_Type
#   - Op base class
#   - R_Op / I_Op / S_Op / B_Op / H_Op

class Instr_Type(MultiValueEnum):
    R_TYPE = Bits(bin='0000', length=4)
    I_TYPE = Bits(bin='0010', length=4)
    S_TYPE = Bits(bin='0110', length=4)
    B_TYPE = Bits(bin='1000', length=4)
    H_TYPE = Bits(bin='1111', length=4)


class Op(Enum):
    pass


# R-Type Operations (opcode: 0000xxx)
class R_Op(Op):
    ADD = Bits(bin='0000000', length=7)   # 0000 000
    SUB = Bits(bin='0000001', length=7)   # 0000 001
    MUL = Bits(bin='0000010', length=7)   # 0000 010


# I-Type Operations (opcode: 0010xxx)
class I_Op(Op):
    LD  = Bits(bin='0010000', length=7)   # 0010 000


# S-Type Operations (opcode: 0110xxx)
class S_Op(Op):
    ST  = Bits(bin='0110000', length=7)   # 0110 000


# B-Type Operations (opcode: 1000xxx)
class B_Op(Op):
    BEQ = Bits(bin='1000000', length=7)   # 1000 000
    BNE = Bits(bin='1000001', length=7)   # 1000 001


# H-Type Operations (opcode: 1111xxx)
class H_Op(Op):
    HALT = Bits(bin='1111111', length=7)  # 1111 111