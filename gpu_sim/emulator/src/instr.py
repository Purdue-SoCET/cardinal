from abc import ABC, abstractmethod
from enum import Enum
from bitstring import Bits
from typing import Union, Optional
import logging
import sys
import math
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
    def eval(self, t_id: int, t_reg: Reg_File):
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
        rdat1 = t_reg.read(self.rs1)
        imm_val = self.imm.int  # Sign-extended immediate

        match self.op:
            # Immediate INT Arithmetic
            case I_Op_0.ADDI:
                result = rdat1.int + imm_val
            
            case I_Op_0.SUBI:
                result = rdat1.int - imm_val
            
            # Immediate Logical Operators
            case I_Op_0.ORI:
                result = rdat1.int | imm_val
            
            # Immediate Comparison
            case I_Op_0.SLTI:
                result = 1 if rdat1.int < imm_val else 0
            
            case _:
                raise NotImplementedError(f"I-Type 0 operation {self.op} not implemented yet or doesn't exist.")

        out = result & 0xFFFFFFFF
        t_reg.write(self.rd, Bits(int=out, length=32))

class I_Instr_1(Instr):
    def __init__(self, op: I_Op_1, rs1: Bits, rd: Bits, imm: Bits) -> None:
        self.op = op
        self.rs1 = rs1
        self.rd = rd
        self.imm = imm

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        rdat1 = t_reg.read(self.rs1)
        imm_val = self.imm.uint  # Unsigned immediate for shifts and unsigned compare

        match self.op:
            case I_Op_1.SLTIU:
                result = 1 if rdat1.uint < imm_val else 0
            
            case I_Op_1.SRLI:
                shift_amount = imm_val & 0x1F  # Mask to 5 bits
                result = rdat1.uint >> shift_amount
            
            case I_Op_1.SRAI:
                shift_amount = imm_val & 0x1F  # Mask to 5 bits
                result = rdat1.int >> shift_amount  # Arithmetic right shift (sign-extends)
            
            case _:
                raise NotImplementedError(f"I-Type 1 operation {self.op} not implemented yet or doesn't exist.")

        out = result & 0xFFFFFFFF
        t_reg.write(self.rd, Bits(int=out, length=32))

class I_Instr_2(Instr):
    def __init__(self, op: I_Op_2, rs1: Bits, rd: Bits, imm: Bits, mem: Mem = None, pc: Bits = None) -> None:
        self.op = op
        self.rs1 = rs1
        self.rd = rd
        self.imm = imm

        if op == I_Op_2.JALR:
            self.pc = pc    # Program counter for JALR
            self.mem = None # Memory is not used for JALR
        else: # op == I_Op_2.LW or op == I_Op_2.LH or op == I_Op_2.LB
            self.pc = None # Program counter not used for LW/LH/LB
            self.mem = mem # Memory object for LW/LH/LB
  
    def eval(self, t_id: int, t_reg: Reg_File) -> Bits:
        rdat1 = t_reg.read(self.rs1)
        imm_val = self.imm.int  # Sign-extended immediate

        match self.op:
            # Memory Read Operations
            case I_Op_2.LW:
                if self.mem is None:
                    raise RuntimeError("Memory object required for LW operation")
                addr = rdat1.int + imm_val
                result = self.mem.read(addr, 4)  # Read 32 bits (4 bytes)

            case I_Op_2.LH:
                if self.mem is None:
                    raise RuntimeError("Memory object required for LH operation")
                addr = rdat1.int + imm_val
                result = self.mem.read(addr, 2)  # Read 16 bits (2 bytes)
                # Sign extend from 16 to 32 bits
                if result & 0x8000:
                    result |= 0xFFFF0000
            
            case I_Op_2.LB:
                if self.mem is None:
                    raise RuntimeError("Memory object required for LB operation")
                addr = rdat1.int + imm_val
                result = self.mem.read(addr, 1)  # Read 8 bits (1 byte)
                # Sign extend from 8 to 32 bits
                if result & 0x80:
                    result |= 0xFFFFFF00
            
            # Jump and Link Register
            case I_Op_2.JALR:
                if self.pc is None:
                    raise RuntimeError("Program counter required for JALR operation")
                # Save return address (PC + 4)
                return_addr = self.pc + 4
                result = return_addr

                # Calculate target address
                target_addr = rdat1.int + imm_val
                self.pc = target_addr
            
            case _:
                raise NotImplementedError(f"I-Type operation {self.op} not implemented yet or doesn't exist.")
            
            t_reg.write(self.rd, Bits(int=result, length=32))
            return self.pc # If op is JALR, the target PC is returned. Otherwise (for LW/LH/LB), None is returned

class F_Instr(Instr):
    def __init__(self, op: F_Op, rs1: Bits, rd: Bits) -> None:
        self.op = op
        self.rs1 = rs1
        self.rd = rd

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        rdat1 = t_reg.read(self.rs1)

        match self.op:
            # Root Operations
            case F_Op.ISQRT:
                # Inverse square root: 1 / sqrt(x)
                val = rdat1.float
                if val <= 0:
                    logger.warning(f"Invalid value for ISQRT from thread ID {t_id}: R{self.rs1.int} = {val}")
                    result = float('inf')
                else:
                    result = 1.0 / math.sqrt(val)
            
            # Trigonometric Operations
            case F_Op.SIN:
                result = math.sin(rdat1.float)
            
            case F_Op.COS:
                result = math.cos(rdat1.float)
            
            # Type Conversion Operations
            case F_Op.ITOF:
                # Integer to Float
                result = float(rdat1.int)
            
            case F_Op.FTOI:
                # Float to Integer (truncate towards zero)
                result = int(rdat1.float)
            
            case _:
                raise NotImplementedError(f"F-Type operation {self.op} not implemented yet or doesn't exist.")

        # Check for overflow in FP operations
        if self.op in [F_Op.ISQRT, F_Op.SIN, F_Op.COS, F_Op.ITOF]:
            if result == float('inf') or result == float('-inf') or result != result:
                logger.warning(f"Infinite/NaN FP result in {self.op.name} from thread ID {t_id}: R{self.rd.int} = {self.op.name}(R{self.rs1.int})")

        # For FTOI, keep as integer; for others, convert properly
        if self.op == F_Op.FTOI:
            out = result & 0xFFFFFFFF
            t_reg.write(self.rd, Bits(int=out, length=32))
        else:
            # For floating point results, write as float
            t_reg.write(self.rd, Bits(float=result, length=32))

class S_Instr_0(Instr):
    def __init__(self, op: S_Op_0, rs1: Bits, rs2: Bits, imm: Bits, mem=None) -> None:
        self.op = op
        self.rs1 = rs1
        self.rs2 = rs2
        self.imm = imm
        self.mem = mem

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        if self.mem is None:
            raise RuntimeError(f"Memory object required for {self.op.name} operation")
        
        rdat1 = t_reg.read(self.rs1)
        rdat2 = t_reg.read(self.rs2)
        imm_val = self.imm.int  # Sign-extended immediate
        
        # Calculate address
        addr = rdat1.int + imm_val

        match self.op:
            # Memory Write Operations
            case S_Op_0.SW:
                # Store Word (32 bits / 4 bytes)
                self.mem.write(addr, rdat2.uint, 4)
            
            case S_Op_0.SH:
                # Store Half-Word (16 bits / 2 bytes)
                data = rdat2.uint & 0xFFFF
                self.mem.write(addr, data, 2)
            
            case S_Op_0.SB:
                # Store Byte (8 bits / 1 byte)
                data = rdat2.uint & 0xFF
                self.mem.write(addr, data, 1)
            
            case _:
                raise NotImplementedError(f"S-Type operation {self.op} not implemented yet or doesn't exist.")

class B_Instr_0(Instr):
    def __init__(self, op: B_Op_0, rs1: Bits, rs2: Bits, pred_dest: Bits, pred_reg=None) -> None:
        self.op = op
        self.rs1 = rs1
        self.rs2 = rs2
        self.pred_dest = pred_dest
        self.pred_reg = pred_reg  # Predicate register file

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        if self.pred_reg is None:
            raise RuntimeError(f"Predicate register required for {self.op.name} operation")
        
        rdat1 = t_reg.read(self.rs1)
        rdat2 = t_reg.read(self.rs2)
        
        # Evaluate branch condition and write result to predicate register
        match self.op:
            # Comparison Operations (write to predicate register)
            case B_Op_0.BEQ:
                # Branch if Equal
                pred_value = 1 if rdat1.int == rdat2.int else 0
            
            case B_Op_0.BNE:
                # Branch if Not Equal
                pred_value = 1 if rdat1.int != rdat2.int else 0
            
            case B_Op_0.BGE:
                # Branch if Greater or Equal (signed)
                pred_value = 1 if rdat1.int >= rdat2.int else 0
            
            case B_Op_0.BGEU:
                # Branch if Greater or Equal (unsigned)
                pred_value = 1 if rdat1.uint >= rdat2.uint else 0
            
            case B_Op_0.BLT:
                # Branch if Less Than (signed)
                pred_value = 1 if rdat1.int < rdat2.int else 0
            
            case B_Op_0.BLTU:
                # Branch if Less Than (unsigned)
                pred_value = 1 if rdat1.uint < rdat2.uint else 0
            
            case _:
                raise NotImplementedError(f"B-Type operation {self.op} not implemented yet or doesn't exist.")
        
        # Write to predicate register: PR[pred_dest][T_ID] = pred_value
        self.pred_reg.write(self.pred_dest, t_id, pred_value)

class U_Instr(Instr):
    def __init__(self, op: U_Op, rd: Bits, imm: Bits, pc: Optional[Bits] = None) -> None:
        self.op = op
        self.rd = rd
        self.imm = imm
        self.pc = pc  # Program counter for AUIPC

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        match self.op:
            # Build PC
            case U_Op.AUIPC:
                # Add Upper Immediate to PC
                if self.pc is None:
                    raise RuntimeError("Program counter required for AUIPC operation")
                result = self.pc.int + (self.imm.int << 12)
                out = result & 0xFFFFFFFF
                t_reg.write(self.rd, Bits(int=out, length=32))
            
            # Building Immediates
            case U_Op.LLI:
                # Load Lower Immediate: R[rd] = {R[rd][31:12], imm[11:0]}
                rd_val = t_reg.read(self.rd)
                upper_bits = rd_val.uint & 0xFFFFF000  # Keep upper 20 bits
                lower_bits = self.imm.uint & 0x00000FFF  # Get lower 12 bits from immediate
                result = upper_bits | lower_bits
                t_reg.write(self.rd, Bits(uint=result, length=32))
            
            case U_Op.LMI:
                # Load Middle Immediate: R[rd] = {R[rd][31:24], imm[11:0], R[rd][11:0]}
                rd_val = t_reg.read(self.rd)
                upper_bits = rd_val.uint & 0xFF000000  # Keep upper 8 bits
                lower_bits = rd_val.uint & 0x00000FFF  # Keep lower 12 bits
                middle_bits = (self.imm.uint & 0x00000FFF) << 12  # Middle 12 bits from immediate
                result = upper_bits | middle_bits | lower_bits
                t_reg.write(self.rd, Bits(uint=result, length=32))
            
            case U_Op.LUI:
                # Load Upper Immediate: R[rd] = {imm[7:0], R[rd][23:0]}
                # Note: imm is 12 bits, but we only use the lower 8 bits
                rd_val = t_reg.read(self.rd)
                lower_bits = rd_val.uint & 0x00FFFFFF  # Keep lower 24 bits
                upper_bits = (self.imm.uint & 0x000000FF) << 24  # Upper 8 bits from immediate
                result = upper_bits | lower_bits
                t_reg.write(self.rd, Bits(uint=result, length=32))
            
            case _:
                raise NotImplementedError(f"U-Type operation {self.op} not implemented yet or doesn't exist.")

class C_Instr(Instr):
    def __init__(self, op: C_Op, rd: Bits, csr: Bits, csr_file=None) -> None:
        self.op = op
        self.rd = rd
        self.csr = csr
        self.csr_file = csr_file  # Control Status Register file

    def eval(self, t_id: int, t_reg: Reg_File) -> None:
        if self.csr_file is None:
            raise RuntimeError(f"CSR file required for {self.op.name} operation")
        
        csr_addr = self.csr.uint

        match self.op:
            # Control Status Register Operations
            case C_Op.CSRR:
                # CSR Read: R[rd] = CSR[csr]
                csr_val = self.csr_file.read(csr_addr)
                t_reg.write(self.rd, Bits(int=csr_val, length=32))
            
            case C_Op.CSRW:
                # CSR Write: CSR[csr] = R[rd]
                rd_val = t_reg.read(self.rd)
                self.csr_file.write(csr_addr, rd_val.int)
            
            case _:
                raise NotImplementedError(f"C-Type operation {self.op} not implemented yet or doesn't exist.")

class J_Instr(Instr):
    def __init__(self, op: J_Op, rd: Bits, pred_dest: Bits, imm: Bits, pc: Optional[Bits] = None, pred_reg=None) -> None:
        self.op = op
        self.rd = rd
        self.pred_dest = pred_dest
        self.imm = imm
        self.pc = pc  # Program counter
        self.pred_reg = pred_reg  # Predicate register file

    def eval(self, t_id: int, t_reg: Reg_File) -> Optional[Bits]:
        match self.op:
            # Jump and Link
            case J_Op.JAL:
                if self.pc is None:
                    raise RuntimeError("Program counter required for JAL operation")
                if self.pred_reg is None:
                    raise RuntimeError("Predicate register required for JAL operation")
                
                # R[rd] = PC + 4
                return_addr = self.pc.int + 4
                t_reg.write(self.rd, Bits(int=return_addr, length=32))
                
                # PR[pred_dest] = 1 (set predicate register)
                self.pred_reg.write(self.pred_dest, t_id, 1)
                
                # Calculate new PC (PC = PC + imm)
                new_pc = self.pc.int + self.imm.int
                return Bits(int=new_pc, length=32)
            
            case _:
                raise NotImplementedError(f"J-Type operation {self.op} not implemented yet or doesn't exist.")
        
        return None

class P_Instr(Instr):
    def __init__(self, op: P_Op, rs1: Bits, rs2: Bits, pc: Optional[Bits] = None, pred_reg=None) -> None:
        self.op = op
        self.rs1 = rs1
        self.rs2 = rs2
        self.pc = pc  # Program counter
        self.pred_reg = pred_reg  # Predicate register file

    def eval(self, t_id: int, t_reg: Reg_File) -> Optional[Bits]:
        match self.op:
            # Jump Predicate Not Zero
            case P_Op.JPNZ:
                if self.pc is None:
                    raise RuntimeError("Program counter required for JPNZ operation")
                if self.pred_reg is None:
                    raise RuntimeError("Predicate register required for JPNZ operation")
                
                # Read predicate register value for this thread
                pred_val = self.pred_reg.read(self.rs1, t_id)
                
                if pred_val == 0:
                    # If predicate is zero, jump: PC = R[rs2]
                    rdat2 = t_reg.read(self.rs2)
                    new_pc = rdat2.int
                    return Bits(int=new_pc, length=32)
                else:
                    # If predicate is not zero, continue: PC = PC + 4
                    new_pc = self.pc.int + 4
                    return Bits(int=new_pc, length=32)
            
            case _:
                raise NotImplementedError(f"P-Type operation {self.op} not implemented yet or doesn't exist.")
        
        return None

class H_Instr(Instr):
    def __init__(self, op: H_Op) -> None:
        self.op = op

    def eval(self, t_id: int, t_reg: Reg_File) -> bool:
        match self.op:
            # Halt Operation
            case H_Op.HALT:
                logger.info(f"HALT instruction executed by thread ID {t_id}")
                return True  # Signal that execution should halt
            
            case _:
                raise NotImplementedError(f"H-Type operation {self.op} not implemented yet or doesn't exist.")
        
        return False
