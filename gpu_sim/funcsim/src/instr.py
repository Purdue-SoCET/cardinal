from abc import ABC, abstractmethod
from enum import Enum
from bitstring import Bits
from typing import Union
import logging

from reg_file import *

logger = logging.getLogger(__name__)

# from funcsim.src.reg_file import Reg_File

# ISA Teal Card (used for Enum declarations): https://docs.google.com/spreadsheets/d/1quvfY0Q_mLP5VfUaNGiiruGoqjCMpCyCKM9KlqbujYM/edit?usp=sharing

# Instruction Type Enum (first 3 MSBs of opcode)
class Instr_Type(Enum):
    R_TYPE = Bits(bin='000', length=3)
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
    ADD = Bits(bin='0000', length=4)
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

class Instr(ABC):
    @abstractmethod
    def __init__(self) -> None:
        pass

    @abstractmethod
    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        pass

    def check_overflow(self, result: Union[int, float], t_id: int) -> None:
        match self.op:
            case R_Op.ADD:
                if result > 2147483647 or result < -2147483648:
                    logger.warning(f"Arithmetic overflow in ADD from thread ID {t_id}: R{self.rd.int} = R{self.rs1.int} + R{self.rs2.int}")
            case R_Op.SUB:
                if result > 2147483647 or result < -2147483648:
                    logger.warning(f"Arithmetic overflow in SUB from thread ID {t_id}: R{self.rd.int} = R{self.rs1.int} - R{self.rs2.int}")
            case R_Op.MUL:
                if result > 2147483647 or result < -2147483648:
                    logger.warning(f"Arithmetic overflow in MUL from thread ID {t_id}: R{self.rd.int} = R{self.rs1.int} * R{self.rs2.int}")
            case R_Op.SLL:
                if result > 2147483647 or result < -2147483648:
                    logger.warning(f"Arithmetic overflow in SLL from thread ID {t_id}: R{self.rd.int} = R{self.rs1.int} << R{self.rs2.int}")
            case R_Op.ADDF:
                if result == float('inf') or result == float('-inf') or result != result:
                    logger.warning(f"Invalid FP result in ADDF from thread ID {t_id}: R{self.rd} = R{self.rs1.int} + R{self.rs2.int}")
            case R_Op.SUBF:
                if result == float('inf') or result == float('-inf') or result != result:
                    logger.warning(f"Invalid FP result in SUBF from thread ID {t_id}: R{self.rd} = R{self.rs1.int} - R{self.rs2.int}")
            case R_Op.MULF:
                if result == float('inf') or result == float('-inf') or result != result:
                    logger.warning(f"Invalid FP result in MULF from thread ID {t_id}: R{self.rd} = R{self.rs1.int} * R{self.rs2.int}")
            case R_Op.DIVF:
                if result == float('inf') or result == float('-inf') or result != result:
                    logger.warning(f"Invalid FP result in DIVF from thread ID {t_id}: R{self.rd} = R{self.rs1.int} / R{self.rs2.int}")

class R_Instr(Instr):
    def __init__(self, op: R_Op, rs1: Bits(length=6), rs2: Bits(length=6), rd: Bits(length=6)) -> None:
        self.op = op
        self.rs1 = rs1
        self.rs2 = rs2
        self.rd = rd

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        rdat1 = t_reg.read(self.rs1)
        rdat2 = t_reg.read(self.rs2)

        match self.op:
            # INT Arithmetic Operations
            case R_Op.ADD:
                result = rdat1.int + rdat2.int # does not handle overflow (Python will auto-expand int size in the case of overflow)
                out = result & 0xFFFFFFFF # does handle overflow by wrapping around
                t_reg.write(self.rd, Bits(int=out, length=32))
            
            case R_Op.SUB:
                result = rdat1.int - rdat2.int
            
            case R_Op.MUL:
                result = rdat1.int * rdat2.int
            
            case R_Op.DIV:
                if rdat2.int == 0:
                    logger.warning(f"Division by zero in DIV from thread ID {t_id}: R{self.rd} =R{self.rs1.uint} / {self.rs2.int}")
                    result = 0
                else:
                    result = rdat1.int // rdat2.int
            
            # Bitwise Logical Operators
            case R_Op.AND:
                result = rdat1.int & rdat2.int
            
            case R_Op.OR:
                result = rdat1.int | rdat2.int
            
            case R_Op.XOR:
                result = rdat1.int ^ rdat2.int
            
            # Comparison Operations
            case R_Op.SLT:
                result = 1 if rdat1.int < rdat2.int else 0
            
            case R_Op.SLTU:
                result = 1 if rdat1.uint < rdat2.uint else 0
            
            # Floating Point Arithmetic Operations
            case R_Op.ADDF:
                result = rdat1.float + rdat2.float
            
            case R_Op.SUBF:
                result = rdat1.float - rdat2.float
            
            case R_Op.MULF:
                result = rdat1.float * rdat2.float
            
            case R_Op.DIVF:
                if rdat2.float == 0.0:
                    logger.warning(f"Division by zero in DIVF from thread ID {t_id}: R{self.rd} = R{self.rs1.int} / R{self.rs2.int}")
                    result = float('inf')
                else:
                    result = rdat1.float / rdat2.float
            
            # Bit Shifting Operations
            case R_Op.SLL:
                shift_amount = rdat2.uint & 0x1F  # Mask to 5 bits
                result = (rdat1.int << shift_amount)
            
            case R_Op.SRL:
                shift_amount = rdat2.uint & 0x1F
                result = rdat1.uint >> shift_amount
            
            case R_Op.SRA:
                shift_amount = rdat2.uint & 0x1F
                result = rdat1.int >> shift_amount  # Python's >> preserves sign for negative numbers
            
            case _:
                raise NotImplementedError(f"R-Type operation {self.op} not implemented yet or doesn't exist.")

        self.check_overflow(result, t_id)

        out = result & 0xFFFFFFFF
        t_reg.write(self.rd, Bits(int=out, length=32))

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
