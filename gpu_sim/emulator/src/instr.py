from abc import ABC, abstractmethod
from enum import Enum
from bitstring import Bits
from typing import Union, Optional
from mem import *
import logging
import sys
import math
from pathlib import Path

# Add project root to path for imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from common.custom_enums import *
from reg_file import *
from mem import *
from predicate_reg_file import *

logger = logging.getLogger(__name__)

class Instr(ABC):
    # @abstractmethod
    def __init__(self, op: Op) -> None:
        self.op = op

    @abstractmethod
    def eval(self, global_thread_id: int, t_reg: Reg_File, mem: Mem=None, pred_reg_file: Predicate_Reg_File=None, csr: int=None) -> bool:
        pass

    def check_overflow(self, result: Union[int, float], global_thread_id: int) -> None:
        match self.op:
            case R_Op_0.ADD:
                if result > 2147483647 or result < -2147483648:
                    logger.warning(f"Arithmetic overflow in ADD from thread ID {global_thread_id}: R{self.rd.int} = R{self.rs1.int} + R{self.rs2.int}")
            case R_Op_0.SUB:
                if result > 2147483647 or result < -2147483648:
                    logger.warning(f"Arithmetic overflow in SUB from thread ID {global_thread_id}: R{self.rd.int} = R{self.rs1.int} - R{self.rs2.int}")
            case R_Op_0.MUL:
                if result > 2147483647 or result < -2147483648:
                    logger.warning(f"Arithmetic overflow in MUL from thread ID {global_thread_id}: R{self.rd.int} = R{self.rs1.int} * R{self.rs2.int}")
            case R_Op_1.SLL:
                if result > 2147483647 or result < -2147483648:
                    logger.warning(f"Arithmetic overflow in SLL from thread ID {global_thread_id}: R{self.rd.int} = R{self.rs1.int} << R{self.rs2.int}")
            case R_Op_1.ADDF:
                if result == float('inf') or result == float('-inf') or result != result:
                    logger.warning(f"Infinite/Nan FP result in ADDF from thread ID {global_thread_id}: R{self.rd} = R{self.rs1.int} + R{self.rs2.int}")
            case R_Op_1.SUBF:
                if result == float('inf') or result == float('-inf') or result != result:
                    logger.warning(f"Infinite/NaN FP result in SUBF from thread ID {global_thread_id}: R{self.rd} = R{self.rs1.int} - R{self.rs2.int}")
            case R_Op_1.MULF:
                if result == float('inf') or result == float('-inf') or result != result:
                    logger.warning(f"Infinite/NaN FP result in MULF from thread ID {global_thread_id}: R{self.rd} = R{self.rs1.int} * R{self.rs2.int}")
            case R_Op_1.DIVF:
                if result == float('inf') or result == float('-inf') or result != result:
                    logger.warning(f"Infinite/NaN FP result in DIVF from thread ID {global_thread_id}: R{self.rd} = R{self.rs1.int} / R{self.rs2.int}")
            case U_Op.AUIPC:
                if result > 2147483647 or result < -2147483648:
                    logger.warning(f"Arithmetic overflow in AUIPC from thread ID {global_thread_id}: R{self.rd.int} = PC + {self.imm.int} << 12")
            # case _:
            #     logger.warning(f"Unknown overflow in operation {self.op} from thread ID {global_thread_id}")
    
    def decode(self, instruction: Bits, pc: Bits) -> None:
        opcode = Bits(bin=instruction.bin[25:29], length=4) # bits 31:27
        funct3 = Bits(bin=instruction.bin[29:32], length=3) # bits 26:24
        rs2  = Bits(bin=instruction.bin[7:13], length=6) #24:19
        rs1  = Bits(bin=instruction.bin[13:19], length=6) #18:13
        rd   = Bits(bin=instruction.bin[19:25], length=6) #12:7
        imm  = Bits(bin=instruction.bin[7:13], length=6)    #default (I-Type). Make sure to shift for B-type
        pred = Bits(bin=instruction.bin[2:8], length=5)
        match Instr_Type(opcode): #things passed into here: instruction (line) itself and PC
            case Instr_Type.R_TYPE_0:
                op = R_Op_0(funct3)
                self = R_Instr_0(op=op, rs1=rs1, rs2=rs2, rd=rd)
                print(f"rtype_0, funct={op}, rs1={rs1.int}, rs2={rs2.int}, rd={rd.uint}")  
            case Instr_Type.R_TYPE_1:
                op = R_Op_1(funct3)
                self = R_Instr_1(op=op, rs1=rs1, rs2=rs2, rd=rd)
                print(f"rtype_1, funct={op}, rd={rd.uint}")  
            case Instr_Type.I_TYPE_0:
                op = I_Op_0(funct3)
                self = I_Instr_0(op=op, rs1=rs1, imm=imm, rd=rd)
                print(f"itype_0, funct={op},rd={rd.int},rs1={rs1.int},imm={imm.int}")
            case Instr_Type.I_TYPE_1:
                op = I_Op_1(funct3)
                self = I_Instr_1(op=op, rs1=rs1, imm=imm, rd=rd)
                print(f"itype_1, funct={op},imm={imm.int}")
            case Instr_Type.I_TYPE_2:
                op = I_Op_2(funct3)
                self = I_Instr_2(op=op, rs1=rs1, imm=imm, rd=rd, pc=pc)
                print(f"itype_2, funct={op}, rd={rd.int}, rs1={rs1.int}, imm={imm.int}")
            case Instr_Type.S_TYPE_0:
                op = S_Op_0(funct3)
                # rs2 = imm #reads rs2 in imm spot
                self = S_Instr_0(op=op, rs1=rs1, rs2=rs2, imm=rd) #reads imm in the normal rd spot
                print(f"stype_0, funct={op},imm={rd.int}, rs1={rs1.int}, rs2={rs2.int}")
            case Instr_Type.B_TYPE_0:
                op = B_Op_0(funct3)
                self = B_Instr_0(op=op, rs1=rs1, rs2=rs2)
                print(f"btype, funct={op}")
            case Instr_Type.U_TYPE:
                op = U_Op(funct3)
                imm = imm + rs1 #concatenate
                self = U_Instr(op=op, imm=imm, rd=rd, pc=pc)
                print(f"utype, funct={op},imm={imm.int}, rd={rd.uint}")
            case Instr_Type.J_TYPE:
                op = J_Op(funct3)
                imm = pred + rs2 + rs1 #rs1 + rs2 + pred #concatenate
                self = J_Instr(op=op, rd=rd, imm=imm, pc=pc)
                print("jtype")
            case Instr_Type.P_TYPE:
                op = P_Op(funct3)
                # self = C_Instr(op=op, rs1=rs1, rs2=rs2, rd=rd)
                print("ptype, not implemented yet")
            case Instr_Type.C_TYPE:
                op = C_Op(funct3)
                self = C_Instr(op=op, rs1=rs1, rs2=rs2, rd=rd)
                print(f"ctype, funct={op}, rs1={rs1.uint}, rs2={rs2.uint}, rd={rd.uint}")
            case Instr_Type.F_TYPE:
                op = F_Op(funct3)
                self = F_Instr(op=op, rs1=rs1, rd=rd)
                print(f"ftype, funct={op},imm={imm.int}")
            case Instr_Type.H_TYPE:
                op=H_Op(funct3)
                self = H_Instr(op=op, funct3=funct3)
                print(f"halt, funct={op}, {funct3}")
            case _:
                print("Undefined opcode")
        return self


class R_Instr_0(Instr):
    def __init__(self, op: R_Op_0, rs1: Bits, rs2: Bits, rd: Bits) -> None:
        super().__init__(op)
        self.rs1 = rs1
        self.rs2 = rs2
        self.rd = rd

    def eval(self, global_thread_id: int, csr: int, t_reg: Reg_File, mem: Mem=None, pred_reg_file: Predicate_Reg_File=None) -> bool:
        rdat1 = t_reg.read(self.rs1)
        rdat2 = t_reg.read(self.rs2)
        match self.op:
            # INT Arithmetic Operations
            case R_Op_0.ADD:
                result = rdat1.int + rdat2.int
            
            case R_Op_0.SUB:
                result = rdat1.int - rdat2.int
            
            case R_Op_0.MUL:
                # print(f"{rdat1.int} * {rdat2.int} = {rdat1.int * rdat2.int}")
                result = rdat1.int * rdat2.int
            
            case R_Op_0.DIV:
                if rdat2.int == 0:
                    logger.warning(f"Division by zero in DIV from thread ID {global_thread_id}: R{self.rd} = R{self.rs1.uint} / {self.rs2.int}")
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

        self.check_overflow(result, global_thread_id)

        t_reg.write(self.rd, Bits(int=result, length=32))
        return None
        
class R_Instr_1(Instr):
    def __init__(self, op: R_Op_1, rs1: Bits, rs2: Bits, rd: Bits) -> None:
        super().__init__(op)
        self.rs1 = rs1
        self.rs2 = rs2
        self.rd = rd

    def eval(self, global_thread_id: int, csr: int, t_reg: Reg_File, mem: Mem=None, pred_reg_file: Predicate_Reg_File=None) -> bool:
        rdat1 = t_reg.read(self.rs1)
        rdat2 = t_reg.read(self.rs2)
        is_float_op = False
        match self.op:
            # Comparison Operations
            case R_Op_1.SLTU:
                result = Bits(int=1, length=32) if rdat1.uint < rdat2.uint else Bits(int=1, length=32)
            
            # Floating Point Arithmetic Operations
            case R_Op_1.ADDF:
                is_float_op = True
                result = rdat1.float + rdat2.float
            
            case R_Op_1.SUBF:
                is_float_op = True
                result = rdat1.float - rdat2.float
            
            case R_Op_1.MULF:
                is_float_op = True
                result = rdat1.float * rdat2.float
            
            case R_Op_1.DIVF:
                is_float_op = True
                if rdat2.float == 0.0:
                    logger.warning(f"Division by zero in DIVF from thread ID {global_thread_id}: R{self.rd} = R{self.rs1.int} / R{self.rs2.int}")
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

        self.check_overflow(result, global_thread_id)

        # out = result & 0xFFFFFFFF #shouldn't need this, since Bits already protects against this
        if is_float_op:
            t_reg.write(self.rd, Bits(float=result, length=32))
        else:
            out = result 
            t_reg.write(self.rd, Bits(int=out, length=32)) #result should already be Bits class
        return None
        # t_reg.write(self.rd, Bits(int=out, length=32))

class I_Instr_0(Instr):
    def __init__(self, op: I_Op_0, rs1: Bits, rd: Bits, imm: Bits) -> None:
        super().__init__(op)
        self.rs1 = rs1
        self.rd = rd
        self.imm = imm

    def eval(self, global_thread_id: int, csr: int, t_reg: Reg_File, mem: Mem=None, pred_reg_file: Predicate_Reg_File=None) -> bool:
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

        out = result
        t_reg.write(self.rd, Bits(int=out, length=32))
        return None

class I_Instr_1(Instr):
    def __init__(self, op: I_Op_1, rs1: Bits, rd: Bits, imm: Bits) -> None:
        super().__init__(op)
        self.rs1 = rs1
        self.rd = rd
        self.imm = imm

    def eval(self, global_thread_id: int, csr: int, t_reg: Reg_File, mem: Mem=None, pred_reg_file: Predicate_Reg_File = None) -> bool:
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
        return None

class I_Instr_2(Instr):
    def __init__(self, op: I_Op_2, rs1: Bits, rd: Bits, imm: Bits, pc: Bits = None) -> None:
        super().__init__(op)
        self.rs1 = rs1
        self.rd = rd
        self.imm = imm

        if op == I_Op_2.JALR:
            self.pc = pc    # Program counter for JALR
            # self.mem = None # Memory is not used for JALR
        else: # op == I_Op_2.LW or op == I_Op_2.LH or op == I_Op_2.LB
            self.pc = None # Program counter not used for LW/LH/LB
            # self.mem = mem # Memory object for LW/LH/LB
  
    def eval(self, global_thread_id: int, csr: int, t_reg: Reg_File, mem: Mem, pred_reg_file=None) -> bool:
        # if(self.op != I_Op_2.JALR):
        rdat1 = t_reg.read(self.rs1) #jalr doesn't read from reg file?
        imm_val = self.imm.int  # Sign-extended immediate

        if self.op == I_Op_2.JALR:
            mem = None # Memory is not used for JALR

        match self.op:
            # Memory Read Operations
            case I_Op_2.LW:
                # if mem is None:
                #     raise RuntimeError("Memory object required for LW operation")
                addr = rdat1.int + imm_val
                result = mem.read(addr, 4)  # Read 32 bits (4 bytes)

            case I_Op_2.LH:
                # if self.mem is None:
                #     raise RuntimeError("Memory object required for LH operation")
                addr = rdat1.int + imm_val
                result = mem.read(addr, 2)  # Read 16 bits (2 bytes)
                # Sign extend from 16 to 32 bits
                if result & 0x8000:
                    result |= 0xFFFF0000
            
            case I_Op_2.LB:
                # if self.mem is None:
                #     raise RuntimeError("Memory object required for LB operation")
                addr = rdat1.int + imm_val
                result = mem.read(addr, 1)  # Read 8 bits (1 byte)
                # Sign extend from 8 to 32 bits
                if result & 0x80:
                    result |= 0xFFFFFF00
            
            # Jump and Link Register
            case I_Op_2.JALR:
                print(self.pc)
                if self.pc is None:
                    raise RuntimeError("Program counter required for JALR operation")
                # Save return address (PC + 4)
                return_addr = self.pc.int + 4
                result = return_addr

                # Calculate target address
                target_addr = rdat1.int + imm_val
                self.pc = Bits(int=target_addr, length=32)
                print(type(self.pc))
            
            case _:
                raise NotImplementedError(f"I-Type operation {self.op} not implemented yet or doesn't exist.")
        # print(f"loading x{self.rd.int}={hex(result)} from MEM[{hex(addr)}]")
        t_reg.write(self.rd, Bits(int=result, length=32))
        return None
        # return None.pc # If op is JALR, the target PC is returned. Otherwise (for LW/LH/LB), None is returned

class F_Instr(Instr):
    def __init__(self, op: F_Op, rs1: Bits, rd: Bits) -> None:
        super().__init__(op)
        self.rs1 = rs1
        self.rd = rd

    def eval(self, global_thread_id: int, csr: int, t_reg: Reg_File, mem: Mem=None, pred_reg_file: Predicate_Reg_File=None) -> bool:
        rdat1 = t_reg.read(self.rs1)

        match self.op:
            # Root Operations
            case F_Op.ISQRT:
                # Inverse square root: 1 / sqrt(x)
                val = rdat1.float
                if val <= 0:
                    logger.warning(f"Invalid value for ISQRT from thread ID {global_thread_id}: R{self.rs1.int} = {val}")
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
                logger.warning(f"Infinite/NaN FP result in {self.op.name} from thread ID {global_thread_id}: R{self.rd.int} = {self.op.name}(R{self.rs1.int})")

        # For FTOI, keep as integer; for others, convert properly
        if self.op == F_Op.FTOI:
            out = result & 0xFFFFFFFF
            t_reg.write(self.rd, Bits(int=out, length=32))
        else:
            # For floating point results, write as float
            t_reg.write(self.rd, Bits(float=result, length=32))
        return None

class S_Instr_0(Instr):
    def __init__(self, op: S_Op_0, rs1: Bits, rs2: Bits, imm: Bits) -> None:
        super().__init__(op)
        self.rs1 = rs1
        self.rs2 = rs2
        self.imm = imm

    def eval(self, global_thread_id: int, csr: int, t_reg: Reg_File, mem: Mem, pred_reg_file=None) -> bool:
        rdat1 = t_reg.read(self.rs1)
        rdat2 = t_reg.read(self.rs2)
        imm_val = self.imm.int  # Sign-extended immediate
        
        # Calculate address
        addr = rdat1.int + imm_val
        # print(f"{addr}, rdat1={rdat1}, rdat2={rdat2}")
        match self.op:
            # Memory Write Operations
            case S_Op_0.SW:
                # Store Word (32 bits / 4 bytes)
                mem.write(addr, rdat2.uint, 4)
            
            case S_Op_0.SH:
                # Store Half-Word (16 bits / 2 bytes)
                data = rdat2.uint & 0xFFFF
                mem.write(addr, data, 2)
            
            case S_Op_0.SB:
                # Store Byte (8 bits / 1 byte)
                data = rdat2.uint & 0xFF
                mem.write(addr, data, 1)
            
            case _:
                raise NotImplementedError(f"S-Type operation {self.op} not implemented yet or doesn't exist.")
        return None

class B_Instr_0(Instr):
    def __init__(self, op: B_Op_0, rs1: Bits, rs2: Bits) -> None:
        super().__init__(op)
        self.rs1 = rs1
        self.rs2 = rs2
        # self.pred_reg_file = pred_reg_file

    def eval(self, global_thread_id: int, csr: int, t_reg: Reg_File, mem: Mem=None, pred_reg_file: Predicate_Reg_File=None) -> bool:
        rdat1 = t_reg.read(self.rs1)
        rdat2 = t_reg.read(self.rs2)
        
        # Evaluate branch condition and write result to predicate register
        match self.op:
            # Comparison Operations (write to predicate register)
            case B_Op_0.BEQ:
                # Branch if Equal
                result = 1 if rdat1.int == rdat2.int else 0
            
            case B_Op_0.BNE:
                # Branch if Not Equal
                result = 1 if rdat1.int != rdat2.int else 0
            
            case B_Op_0.BGE:
                # Branch if Greater or Equal (signed)
                result = 1 if rdat1.int >= rdat2.int else 0
            
            case B_Op_0.BGEU:
                # Branch if Greater or Equal (unsigned)
                result = 1 if rdat1.uint >= rdat2.uint else 0
            
            case B_Op_0.BLT:
                # Branch if Less Than (signed)
                result = 1 if rdat1.int < rdat2.int else 0
            
            case B_Op_0.BLTU:
                # Branch if Less Than (unsigned)
                result = 1 if rdat1.uint < rdat2.uint else 0
            
            case _:
                raise NotImplementedError(f"B-Type operation {self.op} not implemented yet or doesn't exist.")

        # Write to predicate register: PR[local_thread_id] = result
        pred_reg_file.write(global_thread_id, Bits(uint=result, length=1))
        if(result):
            print(f"Thread{global_thread_id}: branch taken")
        else:
            # print(f"Thread{global_thread_id}: branch not taken")
            pass
        return None

class U_Instr(Instr):
    def __init__(self, op: U_Op, rd: Bits, imm: Bits, pc: Bits = None) -> None:
        super().__init__(op)
        self.rd = rd
        self.imm = imm
        self.pc = pc  # Program counter for AUIPC

    def eval(self, global_thread_id: int, csr: int, t_reg: Reg_File, mem: Mem=None, pred_reg_file: Predicate_Reg_File=None) -> bool:
        match self.op:
            # Build PC
            case U_Op.AUIPC:
                # Add Upper Immediate to PC
                if self.pc is None:
                    raise RuntimeError("Program counter required for AUIPC operation")
                result = self.pc.int + (self.imm.int << 12)
                self.check_overflow(result, global_thread_id)
                t_reg.write(self.rd, Bits(int=result, length=32))
                
            
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
        # print(f"x{self.rd.int}={result}")
        return None

class C_Instr(Instr):
    def __init__(self, op: C_Op, rd: Bits, rs1: Bits, rs2: Bits) -> None:
        super().__init__(op)
        self.rd = rd
        self.rs1 = rs1
        self.rs2 = rs2
        # self.csr = csr
        # self.csr_file = csr_file  # Control Status Register file

    def eval(self, global_thread_id: int, csr: int, t_reg: Reg_File, mem: Mem=None, pred_reg_file: Predicate_Reg_File=None) -> bool:
        if csr is None:
            raise RuntimeError(f"CSR file required for {self.op.name} operation")
        
        # csr_addr = {self.rs1, self.rs2}
        # print(f"csr_addr={csr_addr}")

        # match self.op:
        #     # Control Status Register Operations
        #     case C_Op.CSRR:
                # CSR Read: R[rd] = CSR[csr]
        csr_tid = csr["tid"]
        csr_val = csr_tid[global_thread_id] #global is actually local...
        t_reg.write(self.rd, Bits(int=csr_val, length=32))
        # print(f"x{self.rd.int}(rd)={csr_val}")
            
            # case C_Op.CSRW:
            #     # CSR Write: CSR[csr] = R[rd]
            #     rd_val = t_reg.read(self.rd)
            #     # self.csr_file.write(csr_addr, rd_val.int)
            
            # case _:
            #     raise NotImplementedError(f"C-Type operation {self.op} not implemented yet or doesn't exist.")
        return None

class J_Instr(Instr):
    def __init__(self, op: J_Op, rd: Bits, imm: Bits, pc: Bits) -> None:
        super().__init__(op)
        self.rd = rd
        self.imm = imm
        self.pc = pc  # Program counter
        # self.pred_reg_file = pred_reg_file  # Predicate register file

    def eval(self, global_thread_id: int, csr: int, t_reg: Reg_File, mem: Mem=None, pred_reg_file: Predicate_Reg_File=None) -> bool:
        match self.op:
            # Jump and Link
            case J_Op.JAL:
                # R[rd] = PC + 4
                return_addr = self.pc.int + 4
                # self.pc = Bits(int=self.pc.int + 4, length=32)

                # Set all predicate registers to 1
                pred_reg_file.write_all(data=Bits(uint=1,length=1))  # writes to all 32 registers
                
                # Calculate new PC (PC = PC + imm)
                self.pc = Bits(int=self.pc.int + self.imm.int, length=32)
                t_reg.write(self.rd, Bits(int=return_addr, length=32))

            case _:
                raise NotImplementedError(f"J-Type operation {self.op} not implemented yet or doesn't exist.")
        
        # t_reg.write(self.rd, Bits(int=self.pc.int, length=32))
        return None
        # return None.pc

class P_Instr(Instr):
    def __init__(self, op: P_Op, rs1: Bits, rs2: Bits, pc: Bits, pred_reg_file: Predicate_Reg_File) -> None:
        super().__init__(op)
        self.rs1 = rs1
        self.rs2 = rs2
        self.pc = pc  # Program counter
        self.pred_reg_file = pred_reg_file  # Predicate register file

    def eval(self, global_thread_id: int, csr: int, t_reg: Reg_File, mem: Mem=None, pred_reg_file: Predicate_Reg_File=None) -> bool:
        match self.op:
            # Jump Predicate Not Zero
            case P_Op.JPNZ:      
                # Read predicate register value
                pred_val = self.pred_reg_file.read(self.rs1)
                
                if pred_val == 0:
                    # If predicate is zero, jump: PC = R[rs2]
                    rdat2 = t_reg.read(self.rs2)
                    self.pc = Bits(int=rdat2.int, length=32)
                else:
                    # If predicate is not zero, continue: PC = PC + 4
                    self.pc = Bits(int=self.pc.int + 4, length=32)
            case _:
                raise NotImplementedError(f"P-Type operation {self.op} not implemented yet or doesn't exist.")
        return None
        # return self.pc

class H_Instr(Instr): #returns true
    def __init__(self, op: H_Op, funct3: Bits, r_pred: Bits = Bits(bin='11111', length=5)) -> None:
        super().__init__(op)
        self.funct3 = funct3

    def eval(self, global_thread_id: int, csr: int, t_reg: Reg_File, mem: Mem=None, pred_reg_file: Predicate_Reg_File=None) -> bool:
        # print(f"{self.funct3}, {self.op}")
        return True
        # match self.op:
        #     # `Halt` Operation
        #     case H_Op.HALT:
        #         print(f"HALT instruction executed by thread ID {global_thread_id}")
        #         return True  # Signal that execution should halt
            
        #     case _:
        #         raise NotImplementedError(f"H-Type operation {self.op} not implemented yet or doesn't exist.")
        
        # return False
