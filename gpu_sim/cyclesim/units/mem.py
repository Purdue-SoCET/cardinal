import sys
from pathlib import Path

parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

from base import LatchIF, Stage, Instruction, MemRequest
from Memory import Mem
from typing import Any, Dict, Optional
from bitstring import Bits


class MemArbiterStage(Stage):
    """
    Arbitrate I$ + D$ request latches into a single request latch feeding MemController.
    Adds req["src"] = "icache" | "dcache" for response routing.
    """

    def __init__(
        self,
        name: str,
        ic_req_latch: LatchIF,
        dc_req_latch: LatchIF,
        mem_req_out_latch: LatchIF,     # -> MemController.behind_latch
        policy: str = "rr",             # "rr" or "icache_prio"
    ):
        super().__init__(name=name, behind_latch=None, ahead_latch=None)
        self.ic_req_latch = ic_req_latch
        self.dc_req_latch = dc_req_latch
        self.mem_req_out_latch = mem_req_out_latch
        self.policy = policy
        self.rr = 0  # 0 prefer I$ first, 1 prefer D$ first

    def _pick(self):
        ic_valid = bool(self.ic_req_latch and self.ic_req_latch.valid)
        dc_valid = bool(self.dc_req_latch and self.dc_req_latch.valid)

        if self.policy == "icache_prio":
            if ic_valid:
                return self.ic_req_latch, "icache"
            if dc_valid:
                return self.dc_req_latch, "dcache"
            return None, None

        # round-robin
        if self.rr == 0:
            if ic_valid:
                return self.ic_req_latch, "icache"
            if dc_valid:
                return self.dc_req_latch, "dcache"
        else:
            if dc_valid:
                return self.dc_req_latch, "dcache"
            if ic_valid:
                return self.ic_req_latch, "icache"

        print(f"[{self.name}] GOT REQUEST FROM ICACHE: {ic_valid}, and DCACHE: {dc_valid}\n")
        return None, None

    def compute(self, input_data=None):
        if not self.mem_req_out_latch.ready_for_push():
            return

        src_latch, src = self._pick()
        if src_latch is None:
            return

        req = src_latch.pop()
        if not isinstance(req, dict):
            raise TypeError(f"[MemArbiterStage] expected dict req, got {type(req)}")

        # tag for response routing
        req["src"] = src

        # normalize key names a bit (optional, but helps avoid warp vs warp_id bugs)
        if "warp_id" not in req and "warp" in req:
            req["warp_id"] = req["warp"]

        self.mem_req_out_latch.push(req)

        # Advance RR after a grant
        self.rr ^= 1


class MemController(Stage):
    """
    Memory controller using Mem() backend.
    - Models fixed latency with inflight queue.
    - Completes at most ONE per cycle.
    - Outputs dict responses including src for demux routing.
    """

    def __init__(self, name: str, behind_latch: LatchIF, ahead_latch: LatchIF, mem_backend: Mem, latency: int = 5):
        super().__init__(name=name, behind_latch=behind_latch, ahead_latch=ahead_latch)
        self.mem_backend = mem_backend
        self.latency = int(latency)
        self.inflight: list[MemRequest] = []

    def _payload_to_bits(self, payload, size_hint: int) -> tuple[Bits, int]:
        if payload is None:
            raise ValueError("Write request missing data")

        if isinstance(payload, Bits):
            return payload, len(payload.tobytes())

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

    def _build_min_inst(self, req_info: dict) -> Instruction:
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
        # 1) age inflight
        for req in self.inflight:
            req.remaining -= 1

        # 2) complete at most one
        for req in list(self.inflight):
            if req.remaining > 0:
                continue

            if not self.ahead_latch.ready_for_push():
                return  # stall with req still inflight

            inst = getattr(req, "inst", None)
            src = getattr(req, "src", None)  # "icache" / "dcache"
            if inst is None:
                inst = self._build_min_inst({"pc": req.pc, "uuid": req.uuid, "warp_id": req.warp_id})

            if req.rw_mode == "write":
                data_bits, nbytes = self._payload_to_bits(req.data, req.size)
                self.mem_backend.write(req.addr, data_bits, nbytes)

                resp = {
                    "src": src,
                    "rw_mode": "write",
                    "status": "WRITE_DONE",
                    "addr": req.addr,
                    "size": req.size,
                    "uuid": req.uuid,
                    "warp": req.warp_id,
                    "pc": req.pc,
                    "inst": inst,
                }
                self.ahead_latch.push(resp)

            else:
                data_bits = self.mem_backend.read(req.addr, req.size)

                resp = {
                    "src": src,
                    "rw_mode": "read",
                    "data": data_bits,   # Bits
                    "addr": req.addr,
                    "size": req.size,
                    "uuid": req.uuid,
                    "warp": req.warp_id,
                    "pc": req.pc,
                    "inst": inst,
                }
                self.ahead_latch.push(resp)

            self.inflight.remove(req)
            return  # enforce ONE completion per cycle

        # 3) accept one new request (if available)
        if self.behind_latch and self.behind_latch.valid:
            req_info = self.behind_latch.pop()
            if not isinstance(req_info, dict):
                raise TypeError(f"[MemController] expected dict req_info, got {type(req_info)}")

            # Prefer passing Instruction end-to-end
            inst = req_info.get("inst", None)
            if inst is None:
                inst = self._build_min_inst(req_info)

            pc_int = int(inst.pc) if isinstance(inst.pc, Bits) else int(inst.pc)
            warp_id = req_info.get("warp_id", getattr(inst, "warp", 0))

            mem_req = MemRequest(
                addr=int(req_info["addr"]),
                size=int(req_info.get("size", 4)),
                uuid=int(req_info.get("uuid", getattr(inst, "iid", 0) or 0)),
                warp_id=int(warp_id),
                pc=int(req_info.get("pc", pc_int)),
                data=req_info.get("data", None),
                rw_mode=req_info.get("rw_mode", "read"),
                remaining=self.latency,
            )

            # Attach routing + inst dynamically
            mem_req.inst = inst
            mem_req.src = req_info.get("src", None)

            self.inflight.append(mem_req)


class MemRespDemuxStage(Stage):
    """
    Demux unified memory responses into icache_resp_latch or dcache_resp_latch using resp["src"].
    Expects dict responses produced by MemController above.
    """

    def __init__(self, name: str, behind_latch: LatchIF, ic_resp_latch: LatchIF, dc_resp_latch: LatchIF):
        super().__init__(name=name, behind_latch=behind_latch, ahead_latch=None)
        self.ic_resp_latch = ic_resp_latch
        self.dc_resp_latch = dc_resp_latch

    def compute(self, input_data=None):
        if not self.behind_latch.valid:
            return

        resp = self.behind_latch.snoop()
        if not isinstance(resp, dict):
            raise TypeError(f"[MemRespDemuxStage] expected dict resp, got {type(resp)}")

        src = resp.get("src", None)
        if src == "icache":
            if not self.ic_resp_latch.ready_for_push():
                return
            self.behind_latch.pop()
            self.ic_resp_latch.push(resp)
        elif src == "dcache":
            if not self.dc_resp_latch.ready_for_push():
                return
            self.behind_latch.pop()
            self.dc_resp_latch.push(resp)
        else:
            raise KeyError(f"[MemRespDemuxStage] Missing/invalid resp['src']: {src}")
