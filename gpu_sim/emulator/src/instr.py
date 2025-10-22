from abc import ABC, abstractmethod
from enum import Enum
from bitstring import Bits
from typing import Union
import logging
import sys
from pathlib import Path

# Add parent directory to path to import custom_enums
sys.path.append(str(Path(__file__).parent.parent.parent / 'common'))
from custom_enums import *
from reg_file import *

logger = logging.getLogger(__name__)

class Instr(ABC):
    @abstractmethod
    def __init__(self) -> None:
        pass

    @abstractmethod
    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        pass

    def check_overflow(self, result: Union[int, float], t_id: int) -> None:
        match self.op:
            case R_Op_0.ADD:
                if result > 2147483647 or result < -2147483648:
                    logger.warning(f"Arithmetic overflow in ADD from thread ID {t_id}: R{self.rd.int} = R{self.rs1.int} + R{self.rs2.int}")
            case R_Op_0.SUB:
                if result > 2147483647 or result < -2147483648:
                    logger.warning(f"Arithmetic overflow in SUB from thread ID {t_id}: R{self.rd.int} = R{self.rs1.int} - R{self.rs2.int}")
            case R_Op_0.MUL:
                if result > 2147483647 or result < -2147483648:
                    logger.warning(f"Arithmetic overflow in MUL from thread ID {t_id}: R{self.rd.int} = R{self.rs1.int} * R{self.rs2.int}")
            case R_Op_1.SLL:
                if result > 2147483647 or result < -2147483648:
                    logger.warning(f"Arithmetic overflow in SLL from thread ID {t_id}: R{self.rd.int} = R{self.rs1.int} << R{self.rs2.int}")
            case R_Op_1.ADDF:
                if result == float('inf') or result == float('-inf') or result != result:
                    logger.warning(f"Infinite/Nan FP result in ADDF from thread ID {t_id}: R{self.rd} = R{self.rs1.int} + R{self.rs2.int}")
            case R_Op_1.SUBF:
                if result == float('inf') or result == float('-inf') or result != result:
                    logger.warning(f"Infinite/NaN FP result in SUBF from thread ID {t_id}: R{self.rd} = R{self.rs1.int} - R{self.rs2.int}")
            case R_Op_1.MULF:
                if result == float('inf') or result == float('-inf') or result != result:
                    logger.warning(f"Infinite/NaN FP result in MULF from thread ID {t_id}: R{self.rd} = R{self.rs1.int} * R{self.rs2.int}")
            case R_Op_1.DIVF:
                if result == float('inf') or result == float('-inf') or result != result:
                    logger.warning(f"Infinite/NaN FP result in DIVF from thread ID {t_id}: R{self.rd} = R{self.rs1.int} / R{self.rs2.int}")

class R_Instr_0(Instr):
    def __init__(self, op: R_Op_0, rs1: Bits, rs2: Bits, rd: Bits) -> None:
        self.op = op
        self.rs1 = rs1
        self.rs2 = rs2
        self.rd = rd

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        rdat1 = t_reg.read(self.rs1)
        rdat2 = t_reg.read(self.rs2)

        match self.op:
            # INT Arithmetic Operations
            case R_Op_0.ADD:
                result = rdat1.int + rdat2.int
            
            case R_Op_0.SUB:
                result = rdat1.int - rdat2.int
            
            case R_Op_0.MUL:
                result = rdat1.int * rdat2.int
            
            case R_Op_0.DIV:
                if rdat2.int == 0:
                    logger.warning(f"Division by zero in DIV from thread ID {t_id}: R{self.rd} = R{self.rs1.uint} / {self.rs2.int}")
                    result = 0
                else:
                    result = rdat1.int // rdat2.int
            
            # Bitwise Logical Operators
            case R_Op_0.AND:
                result = rdat1.int & rdat2.int
            
            case R_Op_0.OR:
                result = rdat1.int | rdat2.int
            
            case R_Op_0.XOR:
                result = rdat1.int ^ rdat2.int
            
            # Comparison Operations
            case R_Op_0.SLT:
                result = 1 if rdat1.int < rdat2.int else 0
            
            case _:
                raise NotImplementedError(f"R-Type operation {self.op} not implemented yet or doesn't exist.")

        self.check_overflow(result, t_id)

        out = result & 0xFFFFFFFF
        t_reg.write(self.rd, Bits(int=out, length=32))

class R_Instr_1(Instr):
    def __init__(self, op: R_Op_1, rs1: Bits, rs2: Bits, rd: Bits) -> None:
        self.op = op
        self.rs1 = rs1
        self.rs2 = rs2
        self.rd = rd

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        rdat1 = t_reg.read(self.rs1)
        rdat2 = t_reg.read(self.rs2)

        match self.op:
            # Comparison Operations
            case R_Op_1.SLTU:
                result = 1 if rdat1.uint < rdat2.uint else 0
            
            # Floating Point Arithmetic Operations
            case R_Op_1.ADDF:
                result = rdat1.float + rdat2.float
            
            case R_Op_1.SUBF:
                result = rdat1.float - rdat2.float
            
            case R_Op_1.MULF:
                result = rdat1.float * rdat2.float
            
            case R_Op_1.DIVF:
                if rdat2.float == 0.0:
                    logger.warning(f"Division by zero in DIVF from thread ID {t_id}: R{self.rd} = R{self.rs1.int} / R{self.rs2.int}")
                    result = float('inf')
                else:
                    result = rdat1.float / rdat2.float
            
            # Bit Shifting Operations
            case R_Op_1.SLL:
                shift_amount = rdat2.uint & 0x1F  # Mask to 5 bits
                result = (rdat1.int << shift_amount)
            
            case R_Op_1.SRL:
                shift_amount = rdat2.uint & 0x1F
                result = rdat1.uint >> shift_amount
            
            case R_Op_1.SRA:
                shift_amount = rdat2.uint & 0x1F
                result = rdat1.int >> shift_amount  # Python's >> preserves sign for negative numbers
            
            case _:
                raise NotImplementedError(f"R-Type 1 operation {self.op} not implemented yet or doesn't exist.")

        self.check_overflow(result, t_id)

        out = result & 0xFFFFFFFF
        t_reg.write(self.rd, Bits(int=out, length=32))

class I_Instr_0(Instr):
    def __init__(self, op: I_Op_0, rs1: Bits, rd: Bits, imm: Bits) -> None:
        self.op = op
        self.rs1 = rs1
        self.rd = rd
        self.imm = imm

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        # TODO: Implement I-Type 0 operations (ADDI, SUBI, ORI, SLTI)
        pass

class I_Instr_1(Instr):
    def __init__(self, op: I_Op_1, rs1: Bits, rd: Bits, imm: Bits) -> None:
        self.op = op
        self.rs1 = rs1
        self.rd = rd
        self.imm = imm

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        # TODO: Implement I-Type 1 operations (SLTIU, SRLI, SRAI)
        pass

class I_Instr_2(Instr):
    def __init__(self, op: I_Op_2, rs1: Bits, rd: Bits, imm: Bits) -> None:
        self.op = op
        self.rs1 = rs1
        self.rd = rd
        self.imm = imm

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        # TODO: Implement I-Type 2 operations (LW, LH, LB, JALR)
        pass

class F_Instr(Instr):
    def __init__(self, op: F_Op, rs1: Bits, rd: Bits) -> None:
        self.op = op
        self.rs1 = rs1
        self.rd = rd

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        # TODO: Implement F-Type operations (ISQRT, SIN, COS, ITOF, FTOI)
        pass

class S_Instr_0(Instr):
    def __init__(self, op: S_Op_0, rs1: Bits, rs2: Bits, imm: Bits) -> None:
        self.op = op
        self.rs1 = rs1
        self.rs2 = rs2
        self.imm = imm

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        # TODO: Implement S-Type 0 operations (SW, SH, SB)
        pass

class B_Instr_0(Instr):
    def __init__(self, op: B_Op_0, rs1: Bits, rs2: Bits, pred_dest: Bits) -> None:
        self.op = op
        self.rs1 = rs1
        self.rs2 = rs2
        self.pred_dest = pred_dest

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        # TODO: Implement B-Type 0 operations (BEQ, BNE, BGE, BGEU, BLT, BLTU)
        # Note: B-Type now writes to predicate registers, not PC
        pass

class U_Instr(Instr):
    def __init__(self, op: U_Op, rd: Bits, imm: Bits) -> None:
        self.op = op
        self.rd = rd
        self.imm = imm

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        # TODO: Implement U-Type operations (AUIPC, LLI, LMI, LUI)
        pass

class C_Instr(Instr):
    def __init__(self, op: C_Op, rd: Bits, csr: Bits) -> None:
        self.op = op
        self.rd = rd
        self.csr = csr

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        # TODO: Implement C-Type operations (CSRR, CSRW)
        pass

class J_Instr(Instr):
    def __init__(self, op: J_Op, rd: Bits, pred_dest: Bits, imm: Bits) -> None:
        self.op = op
        self.rd = rd
        self.pred_dest = pred_dest
        self.imm = imm

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        # TODO: Implement J-Type operations (JAL)
        pass

class P_Instr(Instr):
    def __init__(self, op: P_Op, rs1: Bits, rs2: Bits) -> None:
        self.op = op
        self.rs1 = rs1
        self.rs2 = rs2

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        # TODO: Implement P-Type operations (JPNZ)
        pass

class H_Instr(Instr):
    def __init__(self, op: H_Op) -> None:
        self.op = op

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        # TODO: Implement H-Type operations (HALT)
        pass
