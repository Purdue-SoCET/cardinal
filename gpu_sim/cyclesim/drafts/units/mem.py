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
        print("Inflight count:", len(self.inflight))

        # 1. Try completing ONE inflight request per cycle
        for req in list(self.inflight):
            req.remaining -= 1

            if req.remaining <= 0:
                data = self.mem_backend.read(req.addr, req.size)
                print("DEBUG: trying to read from Mem backend @", hex(req.addr))

                if self.ahead_latch.ready_for_push():
                    self.ahead_latch.push({
                        "uuid": req.uuid,
                        "data": data,
                        "warp": req.warp_id,
                        "pc": req.pc
                    })
                    print(f"[{self.name}] Completed read @0x{req.addr:X}")

                self.inflight.remove(req)
                return  # Stop after 1 completion

        # 2. Accept a new request if no completion happened
        if self.behind_latch and self.behind_latch.valid:
            req_info = self.behind_latch.pop()
            mem_req = MemRequest(
                addr=req_info["addr"],
                size=req_info.get("size", 4),
                uuid=req_info.get("uuid", 0),
                warp_id=req_info.get("warp", 0),
                pc=req_info["pc"],
                remaining=self.latency,
            )
            self.inflight.append(mem_req)
            print(f"[{self.name}] Accepted mem req @0x{mem_req.addr:X} lat={self.latency}")


# if __name__ == "__main__":
#     mem_backend = Mem(start_pc=0x1000, \
#     input_file="/home/shay/a/sing1018/Desktop/SoCET_GPU_FuncSim/gpu/gpu_sim/cyclesim/drafts/test.bin",
#     fmt="bin")
#     inst = Instruction(iid=1, pc=0x100, warp=0, warpGroup=0,
#                        opcode=0, rs1=0, rs2=0, rd=0, pred=0, packet=None)
    
#     mem_stage = MemStage(
#         name = "Memory",
#         behind_latch=ICacheMemReqIF,
#         ahead_latch=MemICacheRespIF,
#         mem_backend=mem_backend,
#         latency=50
#     )

#     mem_backend.memory[0x1000] = 0xDEADBEEF
    
#     ICacheMemReqIF.clear_all()
#     MemICacheRespIF.clear_all()

#     # --- Inject one mem request ---
#     ICacheMemReqIF.push({
#         "addr": 0x1000,
#         "size": 4,
#         "uuid": 123,
#         "warp": 0
#     })


#     # --- Simulate cycles ---
#     print("\n--- Unit Test: MemStage ---")
#     for cycle in range(6):
#         print(f"\nCycle {cycle}")
#         mem_stage.compute()

#         # check if a response arrived
#         if MemICacheRespIF.valid:
#             resp = MemICacheRespIF.pop()
#             print("Response:", resp)

#             assert resp["uuid"] == 123
#             assert resp["data"] == 0xDEADBEEF
#             break

