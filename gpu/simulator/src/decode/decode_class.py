
import sys
from pathlib import Path

parent_dir = Path(__file__).resolve().parents[3]

sys.path.append(str(parent_dir))
from simulator.latch_forward_stage import ForwardingIF, LatchIF, Stage, PredRequest, DecodeType
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from bitstring import Bits 

from gpu.common.custom_enums_multi import Instr_Type, R_Op, I_Op, F_Op, S_Op, B_Op, U_Op, J_Op, P_Op, H_Op, C_Op
from gpu.common.custom_enums import Op

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
        if isinstance(op, R_Op) and op in [R_Op.ADD, R_Op.SUB, R_Op.AND, R_Op.OR, R_Op.XOR, 
                                            R_Op.SLT, R_Op.SLTU, R_Op.SLL, R_Op.SRL, R_Op.SRA]:
            for fu_name in self.fust.keys():
                if fu_name.startswith("Alu_int_"):
                    return fu_name
        
        # Integer immediate operations (ADDI, SUBI, ORI, XORI, SLTI, SLTIU, SLLI, SRLI, SRAI)
        if isinstance(op, I_Op) and op in [I_Op.ADDI, I_Op.SUBI, I_Op.ORI, I_Op.XORI, 
                                            I_Op.SLTI, I_Op.SLTIU, I_Op.SLLI, I_Op.SRLI, I_Op.SRAI]:
            for fu_name in self.fust.keys():
                if fu_name.startswith("Alu_int_"):
                    return fu_name
        
        # Integer multiplication
        if isinstance(op, R_Op) and op == R_Op.MUL:
            for fu_name in self.fust.keys():
                if fu_name.startswith("Mul_int_"):
                    return fu_name
        
        # Integer division
        if isinstance(op, R_Op) and op == R_Op.DIV:
            for fu_name in self.fust.keys():
                if fu_name.startswith("Div_int_"):
                    return fu_name
        
        # Floating-point add/sub
        if isinstance(op, R_Op) and op in [R_Op.ADDF, R_Op.SUBF]:
            for fu_name in self.fust.keys():
                if fu_name.startswith("AddSub_float_"):
                    return fu_name
        
        # Floating-point multiplication
        if isinstance(op, R_Op) and op == R_Op.MULF:
            for fu_name in self.fust.keys():
                if fu_name.startswith("Mul_float_"):
                    return fu_name
        
        # Floating-point division
        if isinstance(op, R_Op) and op == R_Op.DIVF:
            for fu_name in self.fust.keys():
                if fu_name.startswith("Div_float_"):
                    return fu_name
        
        # Square root
        if isinstance(op, F_Op) and op == F_Op.ISQRT:
            for fu_name in self.fust.keys():
                if fu_name.startswith("InvSqrt_float_"):
                    return fu_name
        
        # Trigonometric functions (SIN, COS)
        if isinstance(op, F_Op) and op in [F_Op.SIN, F_Op.COS]:
            for fu_name in self.fust.keys():
                if fu_name.startswith("Trig_float_"):
                    return fu_name
        
        # Type conversion (ITOF, FTOI) - typically handled by ALU or special unit
        if isinstance(op, F_Op) and op in [F_Op.ITOF, F_Op.FTOI]:
            # Try Alu first, then any available unit
            for fu_name in self.fust.keys():
                if fu_name.startswith("Alu_int_"):
                    return fu_name
        
        # Load/Store operations
        if isinstance(op, (S_Op, I_Op)) and (op in [S_Op.SW, S_Op.SH, S_Op.SB] or 
                                              op in [I_Op.LW, I_Op.LH, I_Op.LB]):
            for fu_name in self.fust.keys():
                if fu_name.startswith("Ldst_Fu_"):
                    return fu_name
        
        # Branch operations
        if isinstance(op, B_Op):
            for fu_name in self.fust.keys():
                if "Branch" in fu_name or "branch" in fu_name:
                    return fu_name
        
        # Jump operations
        if isinstance(op, (J_Op, I_Op)) and (isinstance(op, J_Op) or op == I_Op.JALR):
            for fu_name in self.fust.keys():
                if "Branch" in fu_name or "branch" in fu_name:
                    return fu_name
        
        # Fallback: return first available Alu if nothing else matches
        for fu_name in self.fust.keys():
            if fu_name.startswith("Alu_int_"):
                return fu_name
        
        # Final fallback: return first available unit
        return next(iter(self.fust.keys()), None)
    
    def _push_instruction_to_next_stage(self, inst):
        if self.ahead_latch.ready_for_push:
            self.ahead_latch.push(inst)
        else:
            print("[Decode] Stalling due to ahead latch not being ready.")
        
        return
    
    def _service_the_incoming_instruction(self) -> None:
        
        inst = None
        if not self.behind_latch.valid:
                print("[Decode] Received nothing valid yet!")
                return inst
        else:
            # pop whatever you need..
            inst = self.behind_latch.pop()
        
        if self.forward_ifs_read["ICache_Decode_Ihit"].pop() is False:
            print("[Decode] Stalling Pipeline due to Icache Miss")
            return inst 


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
        if is_R or is_I or is_F or is_U or is_J or is_P:
            inst.rd = Bits(uint=((raw >> 7) & 0x3F), length=6)

            # Your special P-type rule using LOWER 3 bits of opcode7
            opcode_lower = opcode7 & 0x7
            if is_P and opcode_lower != 0x0:
                inst.rd = None
        else:
            inst.rd = None

        # rs1 present for R/I/F/S/B/P
        if is_R or is_I or is_F or is_S or is_B or is_P:
            inst.rs1 = Bits(uint=(raw >> 13) & 0x3F, length=5)

            opcode_lower = opcode7 & 0x7
            if is_P and opcode_lower not in (0x4, 0x5):
                inst.rs1 = None
                inst.num_operands = 0 ### ADDED ###
        else:
            inst.rs1 = None
            inst.num_operands = 0 ### ADDED ###

        # rs2 present for R/S/B
        if is_R or is_S or is_B:
            inst.rs2 = Bits(uint=(raw >> 19) & 0x3F, length=5)
            inst.num_operands = 2 ### ADDED ###
        else:
            inst.rs2 = None
            inst.num_operands = 1 ### ADDED ###

        # src_pred present for R/I/F/S/U/B (your original intent)
        if is_R or is_I or is_F or is_S or is_U or is_B:
            inst.src_pred = (raw >> 25) & 0x1F
        else:
            inst.src_pred = None

        # dest_pred for B-type (FIXED '=')
        if is_B:
            inst.dest_pred = (raw >> 7) & 0x3F
        else:
            inst.dest_pred = None

        # imm extraction: keep your rules but fix Bits constructors
        if is_I:
            inst.imm = Bits(uint=((raw >> 19) & 0x3F), length=6).int
        elif is_S:
            inst.imm = Bits(uint=((raw >> 7) & 0x3F), length=6).int
        elif is_U:
            inst.imm = Bits(uint=((raw >> 13) & 0xFFF), length=12).int
        elif is_J:
            imm = (raw >> 13) & 0xFFF
            inst.imm = Bits(uint=imm, length=17).int
        elif is_P:
            inst.imm = Bits(uint=((raw >> 13) & 0x7FF), length=11).int
        elif is_H:
            inst.imm = Bits(uint=0x7FFFFF, length=23).int
        else:
            inst.imm = None

        # Map opcode to actual functional unit name from fust
        inst.intended_FU = self.classify_fust_unit(inst.opcode)

        EOP_bit     = (raw >> 31) & 0x1
        EOS_bit     = (raw >> 30) & 0x1

        if decoded_opcode == H_Op.HALT:
            packet_marker = DecodeType.halt
        elif EOP_bit == 1:
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
            
            print(f"[Decode] Initiating PRF Read {pred_req}")

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
        
        # Initialize wdat list for result storage (32 threads per warp)
        if not inst.wdat or len(inst.wdat) == 0:
            inst.wdat = [Bits(uint=0, length=32) for _ in range(32)]
        
        if inst.warp_id % 2 == 0:
            inst.target_bank = 0
        else:
            inst.target_bank = 1

        self._push_instruction_to_next_stage(inst)
        return 
    
    def compute(self, input_data: Optional[Any] = None):
        """Decode the raw instruction word coming from behind_latch."""
        self._service_the_incoming_instruction()
        
        return


       
        
        

