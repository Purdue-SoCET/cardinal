from mem import *
from state import *

from abc import ABC, abstractmethod
from enum import Enum
from bitstring import Bits
from typing import Union, Optional
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

logger = logging.getLogger(__name__)

class Instr(ABC):
    # @abstractmethod
    def __init__(self, op: Op) -> None:
        self.op = op

    @abstractmethod
    def eval(self, csr: CsrRegFile, state: State) -> bool:
        pass

    def check_predication(self, csr: CsrRegFile, state: State) -> bool:
        local_thread_id = csr.get_thread_id()

        # Non-predicated instructions
        if self.op in {H_Op.HALT, I_Op_2.JALR, P_Op.JPNZ, J_Op.JAL}:
            return True  

        return state.pfile.read_thread(self.pred, local_thread_id)


    def check_overflow(self, result: Union[int, float], global_thread_id: int) -> None:
        # TODO: Create a better overflow check system
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
    
    @staticmethod
    def decode(instruction: Bits, pc: Bits) -> 'Instr':
        # TODO: Investigate the indexing and how the hell it works
        opcode = Bits(bin=instruction.bin[25:29], length=4) # bits 31:27
        funct3 = Bits(bin=instruction.bin[29:32], length=3) # bits 26:24
        rs2  = Bits(bin=instruction.bin[7:13], length=6) #24:19
        rs1  = Bits(bin=instruction.bin[13:19], length=6) #18:13
        rd   = Bits(bin=instruction.bin[19:25], length=6) #12:7
        imm  = Bits(bin=instruction.bin[7:13], length=6)    #default (I-Type). Make sure to shift for B-type
        pred = Bits(bin=instruction.bin[2:8], length=5) # TODO: Look at better way to do this

        # TODO: Handle floating point branches - B_TYPE_1
        match Instr_Type(opcode): #things passed into here: instruction (line) itself and PC
            case Instr_Type.R_TYPE_0:
                op = R_Op_0(funct3)
                print(f"rtype_0, funct={op}, rs1={rs1.int}, rs2={rs2.int}, rd={rd.uint}")  
                ret_instr = R_Instr_0(op=op, rs1=rs1, rs2=rs2, rd=rd)
            case Instr_Type.R_TYPE_1:
                op = R_Op_1(funct3)
                print(f"rtype_1, funct={op}, rs1={rs1.int}, rs2={rs2.int}, rd={rd.uint}")  
                ret_instr = R_Instr_1(op=op, rs1=rs1, rs2=rs2, rd=rd)
            case Instr_Type.I_TYPE_0:
                op = I_Op_0(funct3)
                print(f"itype_0, funct={op},rd={rd.int},rs1={rs1.int},imm={imm.int}")
                ret_instr = I_Instr_0(op=op, rs1=rs1, imm=imm, rd=rd)
            case Instr_Type.I_TYPE_1:
                op = I_Op_1(funct3)
                print(f"itype_1, funct={op},imm={imm.int}")
                ret_instr = I_Instr_1(op=op, rs1=rs1, imm=imm, rd=rd)
            case Instr_Type.I_TYPE_2:
                op = I_Op_2(funct3)
                print(f"itype_2, funct={op}, rd={rd.int}, rs1={rs1.int}, imm={imm.int}")
                ret_instr = I_Instr_2(op=op, rs1=rs1, imm=imm, rd=rd, pc=pc)
            case Instr_Type.S_TYPE_0:
                op = S_Op_0(funct3)
                # rs2 = imm #reads rs2 in imm spot
                print(f"stype_0, funct={op},imm={rd.int}, rs1={rs1.int}, rs2={rs2.int}")
                ret_instr = S_Instr_0(op=op, rs1=rs1, rs2=rs2, imm=rd) #reads imm in the normal rd spot
            case Instr_Type.B_TYPE_0:
                op = B_Op_0(funct3)
                ret_instr = B_Instr_0(op=op, rs1=rs1, rs2=rs2, preddest=rd) #reads preddest in the normal rd spot
                print(f"btype, funct={op}")
            case Instr_Type.U_TYPE:
                op = U_Op(funct3)
                imm = imm + rs1 #concatenate
                print(f"utype, funct={op},imm={imm.int}, rd={rd.uint}")
                ret_instr = U_Instr(op=op, imm=imm, rd=rd, pc=pc)
            case Instr_Type.J_TYPE:
                op = J_Op(funct3)
                imm = pred + rs2 + rs1 #rs1 + rs2 + pred #concatenate
                print("jtype")
                ret_instr = J_Instr(op=op, rd=rd, imm=imm, pc=pc)
            case Instr_Type.P_TYPE:
                # TODO: Create P-Type Instruction Class
                raise NotImplementedError("P-Type instruction not implemented yet.")
            case Instr_Type.C_TYPE:
                op = C_Op(funct3)
                print(f"ctype, funct={op}, rs1={rs1.uint}, rd={rd.uint}")
                ret_instr = C_Instr(op=op, csr1=rs1, rd=rd) # TODO: Check up on werid csrr in teal card
            case Instr_Type.F_TYPE:
                op = F_Op(funct3)
                print(f"ftype, funct={op},imm={imm.int}")
                ret_instr = F_Instr(op=op, rs1=rs1, rd=rd)
            case Instr_Type.H_TYPE:
                op=H_Op(funct3)
                print(f"halt, funct={op}, {funct3}")
                ret_instr = H_Instr(op=op, funct3=funct3)
            case _:
                raise NotImplementedError("Instruction type not implemented yet.")
        
        ret_instr.pred = pred
        return ret_instr

    def _to_float(self, bits_obj) -> float:
        # Encapsulate the "flip and read" logic
        return Bits(bytes=bits_obj.bytes[::-1]).float
    
    def _from_float(self, float_val) -> Bits:
        # Encapsulate the "write and flip back" logic
        res = Bits(float=float_val, length=32)
        return Bits(bytes=res.bytes[::-1])

class R_Instr_0(Instr):
    def __init__(self, op: R_Op_0, rs1: Bits, rs2: Bits, rd: Bits) -> None:
        super().__init__(op)
        self.rs1 = rs1
        self.rs2 = rs2
        self.rd = rd

    def eval(self, csr: CsrRegFile, state: State) -> Optional[int]:
        if not self.check_predication(csr, state):
            return None
        
        rdat1 = state.rfile.read(self.rs1)
        rdat2 = state.rfile.read(self.rs2)
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
                    logger.warning(f"Division by zero in DIV from thread ID {csr.get_global_thread_id()}: R{self.rd} = R{self.rs1.uint} / {self.rs2.uint}")
                    result = 0
                else:
                    result = int(rdat1.int / rdat2.int)
            
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

        self.check_overflow(result, csr.get_global_thread_id())
        state.rfile.write(self.rd, Bits(int=result, length=32))
        return None
        
class R_Instr_1(Instr):
    def __init__(self, op: R_Op_1, rs1: Bits, rs2: Bits, rd: Bits) -> None:
        super().__init__(op)
        self.rs1 = rs1
        self.rs2 = rs2
        self.rd = rd

    def eval(self, csr: CsrRegFile, state: State) -> Optional[int]:
        if not self.check_predication(csr, state):
            return None
        
        rdat1 = state.rfile.read(self.rs1)
        rdat2 = state.rfile.read(self.rs2)
        
        match self.op:
            # Comparison Operations
            case R_Op_1.SLTU:
                result = Bits(int=1, length=32) if rdat1.uint < rdat2.uint else Bits(int=0, length=32)
            
            # Floating Point Arithmetic Operations
            case R_Op_1.ADDF:
                rdat1 = self._to_float(rdat1)
                rdat2 = self._to_float(rdat2)
                result = self._from_float(rdat1 + rdat2)
            case R_Op_1.SUBF:
                rdat1 = self._to_float(rdat1)
                rdat2 = self._to_float(rdat2)
                result = self._from_float(rdat1 - rdat2)
            case R_Op_1.MULF:
                rdat1 = self._to_float(rdat1)
                rdat2 = self._to_float(rdat2)
                result = self._from_float(rdat1 * rdat2)
            case R_Op_1.DIVF:
                rdat1 = self._to_float(rdat1)
                rdat2 = self._to_float(rdat2)
                if rdat2 == 0.0:
                    logger.warning(f"Division by zero in DIVF from thread ID {csr.get_global_thread_id()}: R{self.rd} = R{self.rs1.int} / R{self.rs2.int}")
                    result = self._from_float(0.0)
                else:
                    result = self._from_float(rdat1 / rdat2)
            
            # Bit Shifting Operations
            case R_Op_1.SLL:
                shift_amount = rdat2.uint & 0x1F  # Mask to 5 bits
                result = Bits(rdat1.int << shift_amount, length=32)
            case R_Op_1.SRL:
                shift_amount = rdat2.uint & 0x1F
                result = Bits(rdat1.uint >> shift_amount, length=32)
            case R_Op_1.SRA:
                shift_amount = rdat2.uint & 0x1F
                result = Bits(rdat1.int >> shift_amount, length=32)  # Python's >> preserves sign for negative numbers
            
            case _:
                raise NotImplementedError(f"R-Type 1 operation {self.op} not implemented yet or doesn't exist.")

        self.check_overflow(result.float, csr.get_global_thread_id())
        state.rfile.write(self.rd, result)
        return None
    

class I_Instr_0(Instr):
    def __init__(self, op: I_Op_0, rs1: Bits, rd: Bits, imm: Bits) -> None:
        super().__init__(op)
        self.rs1 = rs1
        self.rd = rd
        self.imm = imm

    def eval(self, csr: CsrRegFile, state: State) -> Optional[int]:
        if not self.check_predication(csr, state):
            return None
        
        rdat1 = state.rfile.read(self.rs1)
        imm_val = self.imm.int  # Sign-extended immediate

        match self.op:
            # Immediate INT Arithmetic
            case I_Op_0.ADDI:
                result = rdat1.int + imm_val
            case I_Op_0.SUBI:
                raise NotImplementedError("SUBI has been deprecated in favor of ADDI with negative immediate.")
            
            # Immediate Logical Operators
            case I_Op_0.ORI:
                result = rdat1.int | imm_val
            
            # Immediate Comparison
            case I_Op_0.SLTI:
                result = 1 if rdat1.int < imm_val else 0
            
            case _:
                raise NotImplementedError(f"I-Type 0 operation {self.op} not implemented yet or doesn't exist.")

        state.rfile.write(self.rd, Bits(int=result, length=32))
        return None

class I_Instr_1(Instr):
    def __init__(self, op: I_Op_1, rs1: Bits, rd: Bits, imm: Bits) -> None:
        super().__init__(op)
        self.rs1 = rs1
        self.rd = rd
        self.imm = imm

    def eval(self, csr: CsrRegFile, state: State) -> Optional[int]:
        if not self.check_predication(csr, state):
            return None
        
        rdat1 = state.rfile.read(self.rs1)
        imm_val = self.imm.int # Using signed immediate for set less than instruction

        match self.op:
            case I_Op_1.SLTIU:
                result = 1 if rdat1.uint < (imm_val& 0xFFFFFFFF) else 0
            case I_Op_1.SRLI:
                shift_amount = imm_val & 0x1F  # Mask to 5 bits
                result = rdat1.uint >> shift_amount
            case I_Op_1.SRAI:
                shift_amount = imm_val & 0x1F  # Mask to 5 bits
                result = rdat1.int >> shift_amount  # Arithmetic right shift (sign-extends)
            
            case _:
                raise NotImplementedError(f"I-Type 1 operation {self.op} not implemented yet or doesn't exist.")

        out = result & 0xFFFFFFFF
        state.rfile.write(self.rd, Bits(int=out, length=32))
        return None

class I_Instr_2(Instr):
    def __init__(self, op: I_Op_2, rs1: Bits, rd: Bits, imm: Bits, pc: Bits = None) -> None:
        super().__init__(op)
        self.rs1 = rs1
        self.rd = rd
        self.imm = imm
        self.pc = pc    # Program counter for JALR

    def eval(self, csr: CsrRegFile, state: State) -> Optional[int]:
        if not self.check_predication(csr, state):
            return None
        
        rdat1 = state.rfile.read(self.rs1)
        imm_val = self.imm.int  # Sign-extended immediate

        match self.op:
            # Memory Read Operations
            case I_Op_2.LW:
                addr = rdat1.int + imm_val
                result = (state.mem.read(addr, 4)).int  # Read 32 bits (4 bytes)
            case I_Op_2.LH:
                addr = rdat1.int + imm_val
                result = (state.mem.read(addr, 2)).int  # Read 16 bits (2 bytes)
            case I_Op_2.LB:
                addr = rdat1.int + imm_val
                result = (state.mem.read(addr, 1)).int  # Read 8 bits (1 byte)
  
            # Jump and Link Register
            case I_Op_2.JALR:
                if self.pc is None: raise RuntimeError("Program counter required for JALR operation")

                # Save return address
                result = self.pc.uint + 4
                state.rfile.write(self.rd, Bits(int=result, length=32))

                # Calculate target address and return
                target_addr = rdat1.int + imm_val
                return target_addr & 0xFFFFFFFE  # Ensure LSB is zero (word-aligned)
            
            case _:
                raise NotImplementedError(f"I-Type operation {self.op} not implemented yet or doesn't exist.")
        
        state.rfile.write(self.rd, Bits(int=result, length=32))
        return None

class F_Instr(Instr):
    def __init__(self, op: F_Op, rs1: Bits, rd: Bits) -> None:
        super().__init__(op)
        self.rs1 = rs1
        self.rd = rd

    def eval(self, csr: CsrRegFile, state: State) -> Optional[int]:
        if not self.check_predication(csr, state):
            return None
        
        rdat1 = state.rfile.read(self.rs1)

        match self.op:
            # Root Operations
            case F_Op.ISQRT:
                val = self._to_float(rdat1)
                if val <= 0:
                    logger.warning(f"Invalid value for ISQRT from thread ID {csr.get_global_thread_id()}: R{self.rs1.int} = {val}")
                    result = 0.0
                else:
                    result = 1.0 / math.sqrt(val)
            
            # Trigonometric Operations
            case F_Op.SIN:
                result = math.sin(self._to_float(rdat1))
            case F_Op.COS:
                result = math.cos(self._to_float(rdat1))

            # Type Conversion Operations
            case F_Op.ITOF:
                # Integer to Float
                result = float(rdat1.int)
            case F_Op.FTOI:
                # Float to Integer (truncate towards zero)
                result = int(self._to_float(rdat1))

            case _:
                raise NotImplementedError(f"F-Type operation {self.op} not implemented yet or doesn't exist.")

        # Check for overflow in FP operations - TODO: refine this
        # if self.op in [F_Op.ISQRT, F_Op.SIN, F_Op.COS, F_Op.ITOF]:
        #     if result == float('inf') or result == float('-inf') or result != result:
        #         logger.warning(f"Infinite/NaN FP result in {self.op.name} from thread ID {csr.get_global_thread_id()}: R{self.rd.int} = {self.op.name}(R{self.rs1.int})")

        if self.op == F_Op.FTOI:
            state.rfile.write(self.rd, Bits(int=result, length=32))
        else:
            state.rfile.write(self.rd, self._from_float(result))
        
        return None

class S_Instr_0(Instr):
    def __init__(self, op: S_Op_0, rs1: Bits, rs2: Bits, imm: Bits) -> None:
        super().__init__(op)
        self.rs1 = rs1
        self.rs2 = rs2
        self.imm = imm

    def eval(self, csr: CsrRegFile, state: State) -> Optional[int]:
        if not self.check_predication(csr, state):
            return None
        
        rdat1 = state.rfile.read(self.rs1)
        rdat2 = state.rfile.read(self.rs2)
        imm_val = self.imm.int  # Sign-extended immediate
        
        # Calculate address
        addr = rdat1.int + imm_val
        match self.op:
            # Memory Write Operations
            case S_Op_0.SW: # Store Word (32 bits / 4 bytes)
                state.memory.write(addr, rdat2, 4)
            case S_Op_0.SH: # Store Half-Word (16 bits / 2 bytes)
                data = Bits(int=(rdat2.int & 0xFFFF), length=16)
                state.memory.write(addr, data, 2)
            case S_Op_0.SB: # Store Byte (8 bits / 1 byte)
                data = Bits(int=(rdat2.int & 0xFF), length=8)
                state.memory.write(addr, data, 1)

            case _:
                raise NotImplementedError(f"S-Type operation {self.op} not implemented yet or doesn't exist.")
        return None

class B_Instr_0(Instr):
    def __init__(self, op: B_Op_0, rs1: Bits, rs2: Bits, preddest: Bits) -> None:
        super().__init__(op)
        self.rs1 = rs1
        self.rs2 = rs2
        self.preddest = preddest

    def eval(self, csr: CsrRegFile, state: State) -> Optional[int]:
        if not self.check_predication(csr, state):
            return None
        
        rdat1 = state.rfile.read(self.rs1)
        rdat2 = state.rfile.read(self.rs2)

        # Evaluate branch condition and write result to predicate register
        match self.op:
            # Comparison Operations (write to predicate register)
            case B_Op_0.BEQ: result = 1 if rdat1.int == rdat2.int else 0
            case B_Op_0.BNE: result = 1 if rdat1.int != rdat2.int else 0
            case B_Op_0.BGE: result = 1 if rdat1.int >= rdat2.int else 0
            case B_Op_0.BGEU: result = 1 if rdat1.uint >= rdat2.uint else 0
            case B_Op_0.BLT: result = 1 if rdat1.int < rdat2.int else 0
            case B_Op_0.BLTU: result = 1 if rdat1.uint < rdat2.uint else 0

            case _:
                raise NotImplementedError(f"B-Type operation {self.op} not implemented yet or doesn't exist.")

        state.pfile.write_thread(self.preddest, csr.get_thread_id(), result)
        return None

class U_Instr(Instr):
    def __init__(self, op: U_Op, rd: Bits, imm: Bits, pc: Bits = None) -> None:
        super().__init__(op)
        self.rd = rd
        self.imm = imm
        self.pc = pc # Program counter for AUIPC

    def eval(self, csr: CsrRegFile, state: State) -> Optional[int]:
        if not self.check_predication(csr, state):
            return None
        
        match self.op:
            # Build PC
            case U_Op.AUIPC:
                # Add Upper Immediate to PC
                if self.pc is None:
                    raise RuntimeError("Program counter required for AUIPC operation")
                result = self.pc.int + (self.imm.int << 12)
                self.check_overflow(result, csr.get_global_thread_id())
                state.rfile.write(self.rd, Bits(int=result, length=32))
            
            # Building Immediates
            case U_Op.LLI:
                # Load Lower Immediate: R[rd] = {R[rd][31:12], imm[11:0]}
                rd_val = state.rfile.read(self.rd)
                upper_bits = rd_val.uint & 0xFFFFF000  # Keep upper 20 bits
                lower_bits = self.imm.uint & 0x00000FFF  # Get lower 12 bits from immediate
                result = upper_bits | lower_bits
                state.rfile.write(self.rd, Bits(uint=result, length=32))
            case U_Op.LMI:
                # Load Middle Immediate: R[rd] = {R[rd][31:24], imm[11:0], R[rd][11:0]}
                rd_val = state.rfile.read(self.rd)
                upper_bits = rd_val.uint & 0xFF000000  # Keep upper 8 bits
                lower_bits = rd_val.uint & 0x00000FFF  # Keep lower 12 bits
                middle_bits = (self.imm.uint & 0x00000FFF) << 12  # Middle 12 bits from immediate
                result = upper_bits | middle_bits | lower_bits
                state.rfile.write(self.rd, Bits(uint=result, length=32))
            case U_Op.LUI:
                # Load Upper Immediate: R[rd] = {imm[7:0], R[rd][23:0]}
                # Note: imm is 12 bits, but we only use the lower 8 bits
                rd_val = state.rfile.read(self.rd)
                lower_bits = rd_val.uint & 0x00FFFFFF  # Keep lower 24 bits
                upper_bits = (self.imm.uint & 0x000000FF) << 24  # Upper 8 bits from immediate
                result = upper_bits | lower_bits
                state.rfile.write(self.rd, Bits(uint=result, length=32))
            
            case _:
                raise NotImplementedError(f"U-Type operation {self.op} not implemented yet or doesn't exist.")
        return None

class C_Instr(Instr):
    def __init__(self, op: C_Op, rd: Bits, csr1: Bits) -> None:
        super().__init__(op)
        self.rd = rd
        self.csr1 = csr1

    def eval(self, csr: CsrRegFile, state: State) -> Optional[int]:
        if not self.check_predication(csr, state):
            return None
        
        if (self.op != C_Op.CSRR):
            raise NotImplementedError(f"C-Type operation {self.op} not implemented yet or doesn't exist.")
        
        # Transfer from CSR to Register
        csr_value = csr.read(self.csr1)
        state.rfile.write(self.rd, csr_value)

        return None

class J_Instr(Instr):
    def __init__(self, op: J_Op, rd: Bits, imm: Bits, pc: Bits) -> None:
        super().__init__(op)
        self.rd = rd
        self.imm = imm
        self.pc = pc

    def eval(self, csr: CsrRegFile, state: State) -> Optional[int]:
        if (self.op != J_Op.JAL):
            raise NotImplementedError(f"J-Type operation {self.op} not implemented yet or doesn't exist.")
        
        # Return Register
        return_addr = self.pc.int + 4
        state.rfile.write(self.rd, Bits(int=return_addr, length=32))

        # Update PC
        target_addr = self.pc.int + self.imm.int
        return target_addr & 0xFFFFFFFE  # Ensure LSB is zero (word-aligned)

class P_Instr(Instr):
    def __init__(self, op: P_Op, rs1: Bits, rs2: Bits, pc: Bits, pred_reg_file: PredicateRegFile) -> None:
        raise NotImplementedError(f"P-Type operation {self.op} not implemented yet or doesn't exist.")

    def eval(self, csr: CsrRegFile, state: State) -> bool:
        raise NotImplementedError(f"P-Type operation {self.op} not implemented yet or doesn't exist.")

class H_Instr(Instr): #returns true
    def __init__(self, op: H_Op, funct3: Bits, r_pred: Bits = Bits(bin='11111', length=5)) -> None:
        super().__init__(op)

    def eval(self, csr: CsrRegFile, state: State) -> Optional[int]:
        raise RuntimeError("Attempted to evaluate a HALT instruction.")
        return None
