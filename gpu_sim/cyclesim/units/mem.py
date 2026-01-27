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


class MemController(Stage):
    """Memory controller functional unit using Mem() backend. ONE completion per cycle."""

    def __init__(self, name, behind_latch, ahead_latch, mem_backend: Mem, latency: int = 5):
        super().__init__(name=name, behind_latch=behind_latch, ahead_latch=ahead_latch)
        self.mem_backend = mem_backend
        self.latency = int(latency)
        self.inflight: list[MemRequest] = []

    def _payload_to_bits(self, payload, size_hint: int) -> tuple[Bits, int]:
        """
        Convert store payload into (Bits, nbytes).
        Supports:
          - Bits
          - bytes/bytearray
          - int (encoded little-endian, size_hint bytes)
          - list[int] of 32-bit words (little-endian)
        """
        if payload is None:
            raise ValueError("Write request missing data")

        if isinstance(payload, Bits):
            b = payload.tobytes()
            return payload, len(b)

        if isinstance(payload, (bytes, bytearray)):
            b = bytes(payload)
            return Bits(bytes=b), len(b)

        if isinstance(payload, int):
            n = int(size_hint) if int(size_hint) > 0 else 4
            b = int(payload).to_bytes(n, "little", signed=False)
            return Bits(bytes=b), len(b)

        if isinstance(payload, list):
            bb = bytearray()
            for w in payload:
                bb.extend(int(w).to_bytes(4, "little", signed=False))
            return Bits(bytes=bytes(bb)), len(bb)

        raise TypeError(f"Unsupported write payload type: {type(payload)}")

    def _build_min_inst(self, req_info: dict) -> "Instruction":
        """Fallback builder if caller didn't pass an Instruction."""
        pc_raw = req_info.get("pc", 0)
        pc_bits = pc_raw if isinstance(pc_raw, Bits) else Bits(uint=int(pc_raw), length=32)

        return Instruction(
            iid=req_info.get("uuid", req_info.get("iid", 0)),
            pc=pc_bits,
            intended_FSU=req_info.get("intended_FSU", None),
            warp=req_info.get("warp", req_info.get("warp_id", 0)),
            warpGroup=req_info.get("warpGroup", None),
            opcode=req_info.get("opcode", None),
            rs1=req_info.get("rs1", Bits(uint=0, length=5)),
            rs2=req_info.get("rs2", Bits(uint=0, length=5)),
            rd=req_info.get("rd", Bits(uint=0, length=5)),
        )

    def compute(self, input_data=None):
        # 1) decrement remaining for all inflight
        for req in self.inflight:
            req.remaining -= 1

        # 2) complete at most ONE ready request
        for req in list(self.inflight):
            if req.remaining > 0:
                continue

            # can't push? stall (keep inflight)
            if not self.ahead_latch.ready_for_push():
                return

            inst = getattr(req, "inst", None)  # dynamically attached

            if req.rw_mode == "write": # by defaults services writes before reads
            # which is correct..
                data_bits, nbytes = self._payload_to_bits(req.data, req.size)
                self.mem_backend.write(req.addr, data_bits, nbytes)

                # If you want to mark completion on the Instruction:
                if inst is not None:
                    inst.mem_status = "WRITE_DONE"   # optional dynamic field

                # For pipeline consistency, push Instruction forward if available.
                # Otherwise push a minimal Instruction so downstream doesn't crash.
                self.ahead_latch.push(inst if inst is not None else self._build_min_inst({
                    "pc": req.pc, "uuid": req.uuid, "warp": req.warp_id
                }))

            else:
                # READ
                data_bits = self.mem_backend.read(req.addr, req.size)

                # attach fetched packet to instruction
                if inst is None:
                    # build Instruction if caller didn't provide one
                    inst = self._build_min_inst({"pc": req.pc, "uuid": req.uuid, "warp": req.warp_id})

                inst.packet = data_bits
                self.ahead_latch.push(inst)

            self.inflight.remove(req)
            return  # enforce ONE completion per cycle

        # 3) accept a new request (only if no completion happened this cycle)
        if self.behind_latch and self.behind_latch.valid:
            req_info = self.behind_latch.pop()

            # Prefer passing Instruction object end-to-end
            inst = req_info.get("inst", None)
            if inst is None:
                inst = self._build_min_inst(req_info)

            pc_int = int(inst.pc) if isinstance(inst.pc, Bits) else int(inst.pc)
            warp_id = inst.warp if inst.warp is not None else int(req_info.get("warp", req_info.get("warp_id", 0)))

            print(MemRequest.__module__)
            print(MemRequest.__annotations__)
            mem_req = MemRequest(
                addr=int(req_info["addr"]),                  # BYTE address
                size=int(req_info.get("size", 4)),
                uuid=int(req_info.get("uuid", inst.iid if inst.iid is not None else 0)),
                warp_id=int(req_info.get("warp_id", warp_id)),
                pc=int(req_info.get("pc", pc_int)),
                data=req_info.get("data", None),
                rw_mode=req_info.get("rw_mode", "read"),
                remaining=self.latency,
            )

            # Attach Instruction dynamically (keeps dataclass unchanged)
            mem_req.inst = inst

            self.inflight.append(mem_req)