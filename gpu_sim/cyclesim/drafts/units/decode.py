from base import ForwardingIF, LatchIF, Stage, Instruction, ICacheEntry, MemRequest, FetchRequest, DecodeType
from Memory import Mem
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from collections import deque
from datetime import datetime
from isa_packets import ISA_PACKETS
from bitstring import Bits
from custom_enums_multi import (
    Op,
    R_Op, I_Op, F_Op, S_Op, B_Op, U_Op, C_Op, J_Op, P_Op, H_Op,
)

global_cycle = 0


def decode_opcode(bits7: Bits):
    """
    Map a 7-bit opcode Bits to an Op enum (preferred) or the
    underlying R_Op/I_Op/... enum as a fallback.
    """
    for enum_cls in (R_Op, I_Op, F_Op, S_Op, B_Op, U_Op, C_Op, J_Op, P_Op, H_Op):
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
        self.last_fwd_value = {}

    def compute(self, input_data: Optional[Any] = None):
        """Decode the raw instruction word coming from behind_latch."""

        # If no input_data given, read from behind latch
        if input_data is None:
            if not self.behind_latch.valid:
                return None
            inst = self.behind_latch.snoop()
        else:
            inst = input_data

        # ---------------------------------------------------------
        # 1) Stall if any forwarding IF is explicitly in wait state
        # ---------------------------------------------------------
        for name, fwd_if in self.forward_ifs_read.items():
            if fwd_if.wait:
                print(f"[{self.name}] Stalled due to wait from next stage.")
                return None

        # ---------------------------------------------------------
        # 2) EDGE-TRIGGER forwarding consumption
        # ---------------------------------------------------------
        fwd_values = {}
        for name, f in self.forward_ifs_read.items():
            payload = f.payload
            if payload is None or payload == self.last_fwd_value.get(name):
                continue
            fwd_values[name] = payload
            self.last_fwd_value[name] = payload

        # ---------------------------------------------------------
        # 3) Decode MUST stall on ihit=False (but only on new event)
        # ---------------------------------------------------------
        if "ICache_Decode_Ihit" in fwd_values and fwd_values["ICache_Decode_Ihit"] is False:
            print(f"[{self.name}] Waiting on ICache ihit signal...")
            return None

        # ---------------------------------------------------------
        # 4) Extract the raw instruction bits
        # ---------------------------------------------------------
        #print(f"[{self.name}] Decoding instruction raw {inst}")
        raw_field = inst.packet 
        print(raw_field)

        if isinstance(raw_field, Bits):
            raw = raw_field.uint & 0xFFFFFFFF
        elif isinstance(raw_field, bytes):
            raw = int.from_bytes(raw_field[:4], byteorder="little")
        elif isinstance(raw_field, int):
            raw = raw_field & 0xFFFFFFFF
        elif isinstance(raw_field, str):
            raw = int(raw_field, 0) & 0xFFFFFFFF
        elif isinstance(raw_field, list):
            raw = sum((byte & 0xFF) << (8 * i)
                      for i, byte in enumerate(raw_field[:4])) & 0xFFFFFFFF
        else:
            raise TypeError(f"[{self.name}] Unsupported packet type: {type(raw_field)}")

        # ---------------------------------------------------------
        # 5) Bitfield decode
        # ---------------------------------------------------------
        opcode7 = raw & 0x7F
        rd      = (raw >> 7)  & 0x3F
        rs1     = (raw >> 13) & 0x3F
        mid6    = (raw >> 19) & 0x3F
        pred    = (raw >> 25) & 0x1F

        opcode_bits = Bits(uint=opcode7, length=7)
        inst.opcode = decode_opcode(opcode_bits)

        # Match Instruction type: registers as Bits
        inst.rs1 = Bits(uint=rs1,  length=6)
        inst.rs2 = Bits(uint=mid6, length=6)
        inst.rd  = Bits(uint=rd,   length=6)

        # ---------------------------------------------------------
        # 5b) Control-type (halt/EOP/MOP/Barrier)
        # ---------------------------------------------------------
        EOP_bit     = (raw >> 31) & 0x1
        MOP_bit     = (raw >> 30) & 0x1
        Barrier_bit = (raw >> 29) & 0x1

        inst.type = None
        if opcode_bits == H_Op.HALT.value or inst.opcode == getattr(Op, "HALT", None):
            inst.type = DecodeType.halt
        elif EOP_bit == 1:
            inst.type = DecodeType.EOP
        elif MOP_bit == 1:
            inst.type = DecodeType.MOP
        elif Barrier_bit == 1:
            inst.type = DecodeType.Barrier

        # ---------------------------------------------------------
        # 6) Predicate register file lookup
        # ---------------------------------------------------------
        pred_mask = self.prf.read_predicate(
            prf_rd_en=1,
            prf_rd_wsel=inst.warp,
            prf_rd_psel=pred,
            prf_neg=0
        )

        if pred_mask is None:
            pred_mask = [True] * 32

        inst.pred = [Bits(uint=int(b), length=1) for b in pred_mask]

        # ---------------------------------------------------------
        # 7) Optional write-forwarding to next stage
        # ---------------------------------------------------------
        for name, f in self.forward_ifs_write.items():
            f.push({
                "decoded": True,
                "type": inst.type,
                "pc": inst.pc,
                "warp": inst.warp,
            })

        # ---------------------------------------------------------
        # 8) Bookkeeping + send result forward
        # ---------------------------------------------------------
        global global_cycle
        inst.stage_entry.setdefault("Decode", global_cycle)
        inst.stage_exit["Decode"] = global_cycle + 1
        inst.issued_cycle = inst.issued_cycle or global_cycle

        self.behind_latch.pop()
        self.send_output(inst)
        print(f"[{self.name}] Decoded instruction. Updated inst packed is {inst}")
        return inst
