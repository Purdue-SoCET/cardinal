from abc import ABC, abstractmethod
from enum import Enum
from bitstring import Bits
import logging

logger = logging.getLogger(__name__)

from funcsim.src.reg_file import Reg_File

# Instruction Type Enum (first 3 MSBs of opcode)
class Instr_Type(Enum):
    R_TYPE = Bits(bin='000')
    I_TYPE_1 = Bits(bin='001')
    I_TYPE_2 = Bits(bin='010')
    S_TYPE = Bits(bin='011')
    B_TYPE = Bits(bin='100')
    U_TYPE = Bits(bin='101')
    J_TYPE = Bits(bin='110')
    P_TYPE = Bits(bin='110')  # P shares 110 with J
    C_TYPE = Bits(bin='101')  # C shares 101 with U

# R-Type Operations (opcode: 000)
class R_Op(Enum):
    ADD = Bits(bin='0000')
    SUB = Bits(bin='0001')
    MUL = Bits(bin='0010')
    DIV = Bits(bin='0011')
    AND = Bits(bin='0100')
    OR = Bits(bin='0101')
    XOR = Bits(bin='0110')
    SLT = Bits(bin='0111')
    SLTU = Bits(bin='1000')
    ADDF = Bits(bin='1001')
    SUBF = Bits(bin='1010')
    MULF = Bits(bin='1011')
    DIVF = Bits(bin='1100')
    SLL = Bits(bin='1101')
    SRL = Bits(bin='1110')
    SRA = Bits(bin='1111')

# I-Type Operations (opcode: 001)
class I_Op_1(Enum):
    LW = Bits(bin='0000')
    LH = Bits(bin='0001')
    LB = Bits(bin='0010')
    JALR = Bits(bin='0011')
    ISQRT = Bits(bin='0100')
    SIN = Bits(bin='0101')
    COS = Bits(bin='0110')

# I-Type Operations (opcode: 010)
class I_Op_2(Enum):
    ADDI = Bits(bin='0000')
    SUBI = Bits(bin='0001')
    ITOF = Bits(bin='0010')
    FTOI = Bits(bin='0011')
    ORI = Bits(bin='0101')
    SLTI = Bits(bin='0111')
    SLTIU = Bits(bin='1000')
    SRLI = Bits(bin='1110')
    SRAI = Bits(bin='1111')

# S-Type Operations (opcode: 011)
class S_Op(Enum):
    SW = Bits(bin='0000')
    SH = Bits(bin='0001')
    SB = Bits(bin='0010')

# B-Type Operations (opcode: 100)
class B_Op(Enum):
    BEQ = Bits(bin='0000')
    BNE = Bits(bin='0001')
    BGE = Bits(bin='0010')
    BGEU = Bits(bin='0011')
    BLT = Bits(bin='0100')
    BLTU = Bits(bin='0101')

# U-Type Operations (opcode: 101)
class U_Op(Enum):
    AUIPC = Bits(bin='0000')
    LLI = Bits(bin='0001')
    LMI = Bits(bin='0010')
    LUI = Bits(bin='0100')

# C-Type Operations (opcode: 101)
class C_Op(Enum):
    CSRR = Bits(bin='1000')
    CSRW = Bits(bin='1001')

# J-Type Operations (opcode: 110)
class J_Op(Enum):
    JAL = Bits(bin='0000')

# P-Type Operations (opcode: 110)
class P_Op(Enum):
    JPNZ = Bits(bin='1000')

FP_INPUT_OPS = {R_Op.ADDF, R_Op.SUBF, R_Op.MULF, R_Op.DIVF, I_Op_2.FTOI}

FP_OUTPUT_OPS = {R_Op.ADDF, R_Op.SUBF, R_Op.MULF, R_Op.DIVF, I_Op_2.ITOF, I_Op_1.ISQRT, I_Op_1.SIN, I_Op_1.COS}

class Instr(ABC):
    @abstractmethod
    def __init__(self) -> None:
        pass

    @abstractmethod
    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        pass

    def check_overflow(op: Union[R_Op, I_Op_2], result: Union[int, float]) -> None:
        if op == R_Op.ADD:
            if result > 2147483647 or result < -2147483648:
                logger.warning(f"Arithmetic overflow in ADD: {rdat1.int} + {rdat2.int}")
        elif op == R_Op.SUB:
            if result > 2147483647 or result < -2147483648:
                logger.warning(f"Arithmetic overflow in SUB: {rdat1.int} - {rdat2.int}")
        # Add more checks for other operations as needed

class R_Instr(Instr):
    def __init__(self, op: R_Op, rs1: Bits(size=6), rs2: Bits(size=6), rd: Bits(size=6)) -> None:
        self.op = op
        self.rs1 = rs1
        self.rs2 = rs2
        self.rd = rd

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        rdat1 = t_reg.read(self.rs1)
        rdat2 = t_reg.read(self.rs2)
        
        match self.op:
            case R_Op.ADD:
                result = rdat1.int + rdat2.int
                if result > 2147483647 or result < -2147483648:
                    logger.warning(f"Arithmetic overflow in ADD from thread ID {t_id}: {rdat1.int} + {rdat2.int}")
                
                out = result & 0xFFFFFFFF
                t_reg.write(self.rd, Bits(int=out, length=32))
            
            case _: # default case
                raise NotImplementedError(f"R-Type operation {self.op} not implemented yet or doesn't exist.")

class I_Instr_1(Instr):
    def __init__(self) -> None:
        pass

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        pass

class I_Instr_2(Instr):
    def __init__(self) -> None:
        pass

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        pass

class S_Instr(Instr):
    def __init__(self) -> None:
        pass

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        pass

class B_Instr(Instr):
    def __init__(self) -> None:
        pass

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        pass

class U_Instr(Instr):
    def __init__(self) -> None:
        pass

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        pass

class C_Instr(Instr):
    def __init__(self) -> None:
        pass

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        pass

class J_Instr(Instr):
    def __init__(self) -> None:
        pass

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        pass

class P_Instr(Instr):
    def __init__(self) -> None:
        pass

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        pass
