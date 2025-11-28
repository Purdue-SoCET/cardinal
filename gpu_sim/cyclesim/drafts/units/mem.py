import sys
from pathlib import Path

parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

from base import ForwardingIF, LatchIF, Stage, Instruction, ICacheEntry, MemRequest, FetchRequest, DecodeType
from Memory import Mem
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from collections import deque
from datetime import datetime
from isa_packets import ISA_PACKETS
from bitstring import Bits 

# Add parent directory to module search path
# ------------------------------------------------------------
# MemStage Class (unchanged except for single-completion-per-cycle)
# ------------------------------------------------------------
class MemStage(Stage):
    """Memory controller functional unit using Mem() backend."""

    def __init__(self, name, behind_latch, ahead_latch, mem_backend, latency=100):
        super().__init__(name=name, behind_latch=behind_latch, ahead_latch=ahead_latch)
        self.mem_backend = mem_backend
        self.latency = latency
        self.inflight: list[MemRequest] = []

    def compute(self, input_data=None):
        print(f"\n[{self.name}] Inflight count: {len(self.inflight)}")

        # ======================================================
        # 1. Try completing ONE in-flight request per cycle
        # ======================================================
        for req in list(self.inflight):
            req.remaining -= 1

            if req.remaining <= 0:
                # Read from memory (returns Bits)
                data_bits = self.mem_backend.read(req.addr, req.size)
                print(f"[{self.name}] DEBUG: trying to read from Mem backend @ 0x{req.addr:X}")

                # ----------------------------
                # Retrieve or build Instruction
                # ----------------------------
                inst: Optional[Instruction] = getattr(req, "inst", None)

                if inst is None:
                    # Fallback: construct a minimal Instruction with correct types
                    pc_int = req.pc
                    pc_bits = pc_int if isinstance(pc_int, Bits) else Bits(uint=pc_int, length=32)

                    inst = Instruction(
                        iid=req.uuid,
                        pc=pc_bits,
                        intended_FSU=None,
                        warp=req.warp_id,
                        warpGroup=None,
                        opcode=None,  # placeholder; type hints aren't enforced at runtime
                        rs1=Bits(uint=0, length=5),
                        rs2=Bits(uint=0, length=5),
                        rd=Bits(uint=0, length=5),
                    )

                # Update the instruction with fetched packet
                inst.packet = data_bits  # raw 32-bit instruction as Bits

                # Optionally you could also log or mark timing here:
                # inst.mark_stage_exit(self.name, <cycle>) if you track cycles externally

                # Push UPDATED Instruction forward instead of a dict
                if self.ahead_latch.ready_for_push():
                    self.ahead_latch.push(inst)
                    pc_show = int(inst.pc) if isinstance(inst.pc, Bits) else inst.pc
                    print(f"[{self.name}] Completed read for warp={inst.warp} pc=0x{pc_show:X}")

                self.inflight.remove(req)
                return  # Stop after 1 completion

        # ======================================================
        # 2. Accept a new request if no completion happened
        # ======================================================
        if self.behind_latch and self.behind_latch.valid:
            req_info = self.behind_latch.pop()

            # ------------- pull or build the Instruction -------------
            inst: Optional[Instruction] = req_info.get("inst", None)

            if inst is None:
                # Build minimal Instruction from fields in req_info
                pc_raw = req_info["pc"]
                pc_bits = pc_raw if isinstance(pc_raw, Bits) else Bits(uint=pc_raw, length=32)

                inst = Instruction(
                    iid=req_info.get("iid", None),
                    pc=pc_bits,
                    intended_FSU=req_info.get("intended_FSU", None),
                    warp=req_info.get("warp", None),
                    warpGroup=req_info.get("warpGroup", None),
                    opcode=req_info.get("opcode", None),
                    rs1=req_info.get("rs1", Bits(uint=0, length=5)),
                    rs2=req_info.get("rs2", Bits(uint=0, length=5)),
                    rd=req_info.get("rd", Bits(uint=0, length=5)),
                )

            # Use Instruction values as ground truth
            warp_id = inst.warp if inst.warp is not None else req_info.get("warp", 0)
            pc_int = int(inst.pc) if isinstance(inst.pc, Bits) else int(inst.pc)

            mem_req = MemRequest(
                addr=req_info["addr"],
                size=req_info.get("size", 4),
                uuid=req_info.get("uuid", inst.iid if inst.iid is not None else 0),
                warp_id=warp_id,
                pc=pc_int,
                remaining=self.latency,
            )
            # attach the Instruction so we can update it on completion
            mem_req.inst = inst

            self.inflight.append(mem_req)
            print(f"[{self.name}] Accepted mem req warp={warp_id} pc=0x{pc_int:X} lat={self.latency}")
