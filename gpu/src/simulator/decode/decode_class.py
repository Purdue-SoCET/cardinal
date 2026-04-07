
from builtins import zip
import sys
from pathlib import Path

parent_dir = Path(__file__).resolve().parents[3]

sys.path.append(str(parent_dir))
from simulator.interfaces import ForwardingIF, LatchIF
from simulator.stage import Stage
from simulator.mem_types import PredRequest, DecodeType
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from bitstring import Bits 

from common.custom_enums_multi import Instr_Type, R_Op, I_Op, F_Op, S_Op, B_Op, U_Op, J_Op, P_Op, H_Op, C_Op, Op

global_cycle = 0

def decode_opcode(bits7: Bits):
    """
    Map a 7-bit opcode Bits to an Op enum (preferred) or the
    underlying R_Op/I_Op/... enum as a fallback.
    """
    for enum_cls in (R_Op, I_Op, F_Op, S_Op, B_Op, U_Op, J_Op, P_Op, H_Op):
        for member in enum_cls:
            if member.value == bits7:
                # Prefer unified Op enum if it has the same name
                try:
                    return Op[member.name]
                except KeyError:
                    return member       # fallback: R_Op / I_Op / ...
    # Default: NOP or None
    try:
        return Op.NOP
    except Exception:
        return None


class DecodeStage(Stage):
    """Decode stage that directly uses the Stage base class."""

    def __init__(
        self,
        name: str,
        behind_latch: Optional[LatchIF],
        ahead_latch: Optional[LatchIF],
        prf,
        fust,
        csr_table,
        kernel_base_ptrs,
        forward_ifs_read: Optional[Dict[str, ForwardingIF]] = None,
        forward_ifs_write: Optional[Dict[str, ForwardingIF]] = None,
    ):
        super().__init__(
            name=name,
            behind_latch=behind_latch,
            ahead_latch=ahead_latch,
            forward_ifs_read=forward_ifs_read or {},
            forward_ifs_write=forward_ifs_write or {},
        )
        self.prf = prf  # predicate register file reference
        self.fust = fust
        self.csr_table = csr_table
        self.kernel_base_ptrs = kernel_base_ptrs
    
    def classify_fust_unit(self, op) -> Optional[str]:
        """
        Map an opcode to an actual functional unit name from self.fust.
        Returns the name of an available functional unit that can execute this operation,
        or None if no suitable unit is found.
        """
        if op is None or not self.fust:
            return None

        # Get the opcode name for matching
        op_name = getattr(op, "name", str(op))
        
        # Determine operation type and look for matching functional units
        
        # Integer ALU operations (ADD, SUB, AND, OR, XOR, SLT, SLTU, SLL, SRL, SRA, etc.)
        if op in [
            R_Op.ADD, R_Op.SUB, R_Op.AND, R_Op.OR, R_Op.XOR, 
            R_Op.SLT, R_Op.SLTU, R_Op.SLL, R_Op.SRL, R_Op.SRA,
            R_Op.SGE, R_Op.SGEU, U_Op.LLI, U_Op.LUI, U_Op.AUIPC, 
            U_Op.LMI, C_Op.CSRR, C_Op.CSRW, I_Op.ADDI, I_Op.SUBI, 
            I_Op.ORI, I_Op.XORI, I_Op.SLTI, I_Op.SLTIU, I_Op.SLLI, 
            I_Op.SRLI, I_Op.SRAI
        ]:
            for fu_name in self.fust.keys():
                if fu_name.startswith("Alu_int_"):
                    return fu_name
        
        # Integer multiplication
        if op in [R_Op.MUL]:
            for fu_name in self.fust.keys():
                if fu_name.startswith("Mul_int_"):
                    return fu_name
        
        # Integer division
        if op in [R_Op.DIV]:
            for fu_name in self.fust.keys():
                if fu_name.startswith("Div_int_"):
                    return fu_name
        
        # Floating-point add/sub/slt/sge
        if op in [R_Op.ADDF, R_Op.SUBF, R_Op.SGEF, R_Op.SLTF]:
            for fu_name in self.fust.keys():
                if fu_name.startswith("Alu_float_"):
                    return fu_name

        # Floating-point multiplication
        if op in [R_Op.MULF]:
            for fu_name in self.fust.keys():
                if fu_name.startswith("Mul_float_"):
                    return fu_name
        
        # Floating-point division
        if op in [R_Op.DIVF]:
            for fu_name in self.fust.keys():
                if fu_name.startswith("Div_float_"):
                    return fu_name
        
        # Square root
        if op in [F_Op.ISQRT]:
            for fu_name in self.fust.keys():
                if fu_name.startswith("InvSqrt_float_"):
                    return fu_name
        
        # Trigonometric functions (SIN, COS)
        if op in [F_Op.SIN, F_Op.COS]:
            for fu_name in self.fust.keys():
                if fu_name.startswith("Trig_float_"):
                    return fu_name
        
        # Type conversion (ITOF, FTOI) - handled by the Conv subunit in the SpecialUnit (has type float)
        if op in [F_Op.ITOF, F_Op.FTOI]:
            for fu_name in self.fust.keys():
                if fu_name.startswith("Conv_float_"):
                    return fu_name
        
        # Load/Store operations
        if op in [
            S_Op.SW, S_Op.SH, S_Op.SB, I_Op.LW,
            I_Op.LH, I_Op.LB, P_Op.PRSW, P_Op.PRLW
        ]:
            for fu_name in self.fust.keys():
                if fu_name.startswith("Ldst_Fu_"):
                    return fu_name
        
        # Branch operations
        if op in [
            B_Op.BEQ, B_Op.BNE, B_Op.BLT, B_Op.BGE, 
            B_Op.BLTU, B_Op.BGEU, H_Op.HALT,
        ]:
            for fu_name in self.fust.keys():
                if "Branch" in fu_name:
                    return fu_name
        
        # Jump operations
        if op in [J_Op.JAL, I_Op.JALR, P_Op.JPNZ]:
            for fu_name in self.fust.keys():
                if "Jump" in fu_name:
                    return fu_name
                        
        # Opcode not mapped to an FU, throw an error
        raise ValueError(f"Opcode {op_name} does not have a corresponding functional unit in the decode stage.")
    
    def _push_instruction_to_next_stage(self, inst):
        if self.ahead_latch.ready_for_push:
            self.ahead_latch.push(inst)
        # else:
        #     print("[Decode] Stalling due to ahead latch not being ready.")
        
        return
    
    def _service_the_incoming_instruction(self) -> None:
        
        inst = None
        if not self.behind_latch.valid:
                # print("[Decode] Received nothing valid yet!")
                return inst
        else:
            # pop whatever you need..
            inst = self.behind_latch.pop()

        raw_bits = inst.packet
        print(f"[Decode]: Received Raw Instruction Data: {int.from_bytes(raw_bits, 'little'):08x}")
        # Make the bytes explicit (adapt depending on your Bits type)
        raw_bytes = raw_bits.bytes if hasattr(raw_bits, "bytes") else bytes(raw_bits)

        raw = int.from_bytes(raw_bytes, "little")  # <-- canonical instruction word

        opcode7 = raw & 0x7F

        # bits [6:0]
        opcode7 = raw & 0x7F
        opcode_bits = Bits(uint=opcode7, length=7)

        # ---- decode opcode: match against enum members that store full 7-bit values ----
        decoded_opcode = None
        decoded_family = None  # will hold the enum class (R_Op, I_Op, ...)

        # c_op is left cooked for now
        for enum_cls in (R_Op, I_Op, F_Op, C_Op, S_Op, B_Op, U_Op, J_Op, P_Op, H_Op):
            for member in enum_cls:
                if member.value == opcode_bits:
                    decoded_opcode = member
                    decoded_family = enum_cls
                    break
            if decoded_opcode is not None:
                break

        inst.opcode = decoded_opcode

        # Optional debug:
        # print(f"[Decode] opcode7=0x{opcode7:02x} opcode_bits={opcode_bits.bin} op={decoded_opcode} fam={decoded_family}")

        # ---- derive instruction type from upper 4 bits (optional, but useful) ----
        upper4_bits = Bits(uint=((opcode7 >> 3) & 0xF), length=4)
        instr_type = None
        for t in Instr_Type:
            # MultiValueEnum: membership check works with `in t.values`
            if upper4_bits in t.values:
                instr_type = t
                break

        # ---------------------------------------------------------
        # Field presence rules
        # Use decoded_family (most direct) or instr_type (equivalent).
        # ---------------------------------------------------------

        is_R = (decoded_family is R_Op)
        is_I = (decoded_family is I_Op)
        is_F = (decoded_family is F_Op)
        is_S = (decoded_family is S_Op)
        is_B = (decoded_family is B_Op)
        is_U = (decoded_family is U_Op)
        is_C = (decoded_family is C_Op)
        is_J = (decoded_family is J_Op)
        is_P = (decoded_family is P_Op)
        is_H = (decoded_family is H_Op)

        # rd present for R/I/F/U/J/P (per your intent)
        # if is_R or is_I or is_F or is_U or is_J or is_P:
        # if is_R or is_I or is_F or is_U or is_J or is_P or is_C:
        if is_R or is_I or is_F or is_U or is_J or is_C:
            inst.rd = Bits(uint=((raw >> 7) & 0x3F), length=6)

            # Your special P-type rule using LOWER 3 bits of opcode7
            opcode_lower = opcode7 & 0x7
            if is_P and opcode_lower != 0x0:
                inst.rd = None
        else:
            inst.rd = Bits(uint=0, length=32)

        # rs1 present for R/I/F/S/B/P
        # if is_R or is_I or is_F or is_S or is_B or is_P:
        if is_R or is_I or is_F or is_S or is_B:
            inst.rs1 = Bits(uint=(raw >> 13) & 0x3F, length=6)

            opcode_lower = opcode7 & 0x7
            # if is_P and opcode_lower not in (0x4, 0x5):
            #     inst.rs1 = None
            #     inst.num_operands = 0 ### ADDED ###
        else:
            inst.rs1 = None
            inst.num_operands = 0 ### ADDED ###

        # rs2 present for R/S/B
        if is_R or is_S or is_B:
            # inst.rs2 = Bits(uint=(raw >> 19) & 0x3F, length=5)
            inst.rs2 = Bits(uint=(raw >> 19) & 0x3F, length=6)
            inst.num_operands = 2 ### ADDED ###
        else:
            inst.rs2 = None
            inst.num_operands = 1 ### ADDED ###
        
        if is_J:
            inst.num_operands = 0

        # no operands for csrr instruction
        if is_C:
            inst.num_operands = 0

        # if u type, route the dest reg to be a src reg for concat.
        if is_U:
            if inst.opcode is U_Op.AUIPC:
                inst.num_operands = 0 # don't collect anything from RF
                inst.rdat1 = [inst.pc for _ in range(32)]
            else:
                inst.num_operands = 1 # collect rd reg value for rs1
                inst.rs1 = inst.rd 

        if is_P:
            if inst.opcode is P_Op.JPNZ:
                inst.num_operands = 0
            elif inst.opcode is P_Op.PRLW or inst.opcode is P_Op.PRSW:
                inst.num_operands = 1
                inst.rs1 = Bits(uint=(raw >> 19) & 0x3F, length=6)

        # src_pred present for R/I/F/S/U/B (your original intent)
        # if is_R or is_I or is_F or is_S or is_U or is_B:
        # if is_R or is_I or is_F or is_S or is_B or is_C or is_H or is_U or is_J:
        if is_R or is_I or is_F or is_S or is_B or is_C or is_H or is_U or is_J or inst.opcode is P_Op.JPNZ:
            inst.src_pred = (raw >> 25) & 0x1F
        elif inst.opcode is P_Op.PRSW or inst.opcode is P_Op.PRLW:
            inst.src_pred = None
        else:
            inst.src_pred = 0

        # dest_pred for B-type (FIXED '=')
        # if is_B:
        if is_B or inst.opcode is P_Op.PRLW:
            inst.dest_pred = (raw >> 7) & 0x1F # changed this to 0x1F since 5th bit should always be 0 for PRF access
        else:
            inst.dest_pred = None

        # imm extraction: keep your rules but fix Bits constructors
        if is_I:
            inst.imm = Bits(uint=((raw >> 19) & 0x3F), length=6)
        elif is_S:
            inst.imm = Bits(uint=((raw >> 7) & 0x3F), length=6)
        elif is_U:
            if inst.opcode is U_Op.AUIPC:
                inst.imm = Bits(uint=((raw >> 1) & 0xFFF000), length=24)
            else:
                inst.imm = Bits(uint=((raw >> 13) & 0xFFF), length=12)
        elif is_J:
            inst.imm = Bits(uint=((raw >> 12) & 0x3FFFE), length=18) ### THIS IS CORRECT, ONLY USE THE VALUE OF 8 IF TRYING TO PASS JAL UNIT TEST ###
            # inst.imm = Bits(uint=8, length=18)
        elif is_P:
            # inst.imm = Bits(uint=((raw >> 13) & 0x7FF), length=11)
            if inst.opcode is P_Op.JPNZ:
                # inst.imm = Bits(uint=((raw >> 6) & 0x7FFFE), length=19) # imm = {rs1[24:19], imm[18:12], prd[11:7],  1'b0}
                inst.imm = Bits(uint=((raw >> 12) & 0x1FFE), length=13) ### THIS IS CORRECT, ONLY USE THE VALUE OF 16 IF TRYING TO PASS JPNZ UNIT TEST ###
                # inst.imm = Bits(uint=16, length=13)
            elif inst.opcode is P_Op.PRSW:
                inst.imm = Bits(uint=((raw >> 7) & 0xFFF), length=12) # imm = {imm[18:12], prd[11:7]}
            elif inst.opcode is P_Op.PRLW:
                imm_lower = (raw >> 12) & 0x07F # imm[18:12]
                imm_upper = (raw >> 25) & 0xF80 # prs[29:25]
                inst.imm = Bits(uint=(imm_upper | imm_lower), length=12) # imm = {prs[29:25], imm[18:12]}
        # elif is_H:
        #     # print(f"[Decode] Received HALT")
        #     inst.imm = Bits(uint=0x7FFFFF, length=23)
        else:
            inst.imm = Bits(uint=0x0, length=6)

        # csr_value and csr_param field population (may need to add more values here later)
        if is_C:
            inst.csr_param = Bits(uint=(raw >> 13) & 0x3F, length=6).uint
            if inst.csr_param == 0:
                inst.csr_value = self.csr_table.read_base_id(inst.warp_id)
            elif inst.csr_param == 1:
                inst.csr_value = self.csr_table.read_tb_id(inst.warp_id)
            elif inst.csr_param == 2:
                inst.csr_value = self.csr_table.read_tb_size(inst.warp_id)
            elif inst.csr_param == 3:
                inst.csr_value = self.kernel_base_ptrs.read(0) # hard-coded to 0 for now since assuming only one kernel per SM

        if is_H:
            inst.num_operands = 0 
        # Map opcode to actual functional unit name from fust
        inst.intended_FU = self.classify_fust_unit(inst.opcode)

        EOP_bit     = (raw >> 31) & 0x1
        EOS_bit     = (raw >> 30) & 0x1

        if EOP_bit == 1:
            packet_marker = DecodeType.EOP
        elif EOS_bit == 1:
            packet_marker = DecodeType.EOS
        else:
            packet_marker = DecodeType.MOP

        # the  forwarding happens immediately
        push_pkt = {"type": packet_marker, "warp_id": inst.warp_id, "pc": inst.pc}
        self.forward_ifs_write["Decode_Scheduler_Pckt"].push(push_pkt)

        # -------------------------------------------------------
        # 6) Predicate register file lookup
        # ---------------------------------------------------------
        # indexed by thread id in the teal card?
        pred_req = None
        if inst.src_pred is not None:
            pred_req = PredRequest(
                rd_en=1,
                rd_wrp_sel=inst.warp_id,
                rd_pred_sel=inst.src_pred,
                prf_neg=0,
                remaining=1
            )
            
            # print(f"[Decode] Initiating PRF Read {pred_req}")
            pred_mask = self.prf.read_predicate(
                prf_rd_en=pred_req.rd_en,
                prf_rd_wsel=pred_req.rd_wrp_sel,
                prf_rd_psel=pred_req.rd_pred_sel,
                prf_neg=pred_req.prf_neg
            )

            if pred_mask is None:
                pred_mask = [True] * 32

            # Convert boolean list to Bits objects for pipeline compatibility
            inst.predicate = [Bits(uint=1 if p else 0, length=1) for p in pred_mask]

            #And the active mask with the predicate mask to get the final active mask for the instruction
            inst.predicate = [
                Bits(uint=(p.uint if a else 0), length=1)
                for a, p in zip(inst.active_mask, inst.predicate)
            ]

        if inst.opcode is P_Op.PRSW or inst.opcode is P_Op.PRLW: # need this here so that the PRSW/PRLW mask doesn't get ANDed with the active mask
            inst.predicate = [Bits(uint=1, length=1) if i == 0 else Bits(uint=0, length=1) for i in range(32)]

        # Initialize wdat list for result storage (32 threads per warp)
        if not inst.wdat or len(inst.wdat) == 0:
            inst.wdat = [Bits(uint=0, length=32) for _ in range(32)]
        
        # TODO: ADD LOGIC HERE TO SET inst.target_regfile TO "pred_regfile" IF THE INSTRUCTION WRITES TO PRED REG FILE
        if inst.opcode is B_Op.BEQ or inst.opcode is B_Op.BNE or inst.opcode is P_Op.PRLW:
            inst.target_regfile = "pred_regfile"
            inst.target_bank = 1 # for now, just hardcoding all pred reg file writes to go to bank 1 and all int/float reg file writes to go to bank 0, but this can be changed later if we want more flexible mapping of logical register files to physical banks
        else:
            if inst.warp_id % 2 == 0:
                inst.target_bank = 0
                inst.target_regfile = "regfile"
            else:
                inst.target_bank = 1
                inst.target_regfile = "regfile"

        self._push_instruction_to_next_stage(inst)
        if inst.opcode is U_Op.LLI:
            print(inst)
        return 
    
    def compute(self, input_data: Optional[Any] = None):
        """Decode the raw instruction word coming from behind_latch."""
        self._service_the_incoming_instruction()
        
        return
    