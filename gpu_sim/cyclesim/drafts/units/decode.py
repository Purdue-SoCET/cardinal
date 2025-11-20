from base import ForwardingIF, LatchIF, Stage, Instruction, ICacheEntry, MemRequest, FetchRequest, DecodeType
from Memory import Mem
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from collections import deque
from datetime import datetime
from isa_packets import ISA_PACKETS
from bitstring import Bits 
global_cycle = 0

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

        # No new instruction presented → do nothing
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
        #    Only handle NEW forwarded events.
        # ---------------------------------------------------------
        fwd_values = {}
        for name, f in self.forward_ifs_read.items():

            payload = f.payload

            # skip if no payload OR same as last seen
            if payload is None or payload == self.last_fwd_value.get(name):
                continue

            # NEW forwarding event detected
            fwd_values[name] = payload
            self.last_fwd_value[name] = payload

        # ---------------------------------------------------------
        # 3) Decode MUST stall on ihit=False (but only on new event)
        # ---------------------------------------------------------
        if "ICache_Decode_Ihit" in fwd_values and fwd_values["ICache_Decode_Ihit"] is False:
            print(f"[{self.name}] Waiting on ICache ihit signal...")
            return None

        # ---------------------------------------------------------
        # 4) Extract the raw instruction bits (supports Bits/int/bytes/etc)
        # ---------------------------------------------------------
        raw_field = inst.packet

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

        opcode_map = {
            0b0000000:"add", 0b0000001:"sub", 0b0000010:"mul",
            0b0000011:"div", 0b0100000:"lw",  0b0110000:"sw",
            0b1000000:"beq", 0b1100000:"jal", 0b1111111:"halt",
        }

        inst.opcode = opcode_map.get(opcode7, "nop")
        inst.rs1 = rs1
        inst.rs2 = mid6
        inst.rd  = rd

        # Default = normal ALU instruction
        inst.type = None #default until overwritten
        EOP_bit = (raw >> 31) & 0x1
        MOP_bit = (raw >> 30) & 0x1
        Barrier_bit = (raw >> 29) & 0x1

        if opcode7 == 0b1111111:
            inst.type = DecodeType.halt

        elif EOP_bit == 1:
            inst.type = DecodeType.EOP

        elif MOP_bit == 1:
            inst.type = DecodeType.MOP

        elif Barrier_bit == 1:
            inst.type = DecodeType.Barrier

        else:
            inst.type = None  # or normal instruction type if you have one


        # ---------------------------------------------------------
        # 6) Predicate register file lookup
        # ---------------------------------------------------------
        pred_mask = self.prf.read_predicate(
            prf_rd_en=1,
            prf_rd_wsel=inst.warp,
            prf_rd_psel=pred,
            prf_neg=0
        )
        inst.pred = pred_mask or [True] * 32

        # ---------------------------------------------------------
        # 7) Optional write-forwarding to next stage
        # ---------------------------------------------------------
        for name, f in self.forward_ifs_write.items():
            f.push({
                "decoded": True,
                "type": inst.type,
                "pc": inst.pc,
                "warp": inst.warp
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
        return inst
