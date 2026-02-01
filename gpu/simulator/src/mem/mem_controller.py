import sys
from pathlib import Path

parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

from base import LatchIF, Stage, Instruction, MemRequest
from Memory import Mem
from typing import Any, Dict, Optional, Deque, Tuple
from bitstring import Bits


class MemController(Stage):
    """
    MemController (NO request queues; pure latch-based backpressure)

    Key semantics:
    - No pending_ic/pending_dc buffering inside the controller.
    - Controller only POPs an input latch when it can immediately start servicing
      the request (capacity gate via max_inflight).
    - If controller is busy, it does NOT pop, so the input latch stays valid and
      upstream naturally stalls via LatchIF.ready_for_push() == False.
    - Fixed latency model using inflight requests with countdown.
    - Completes at most ONE request per cycle (pushes one response) to the correct
      response latch (ic_serve_latch or dc_serve_latch).
    - policy: "rr" or "icache_prio" controls arbitration when both latches valid.
    """

    def __init__(
        self,
        name: str,
        ic_req_latch: LatchIF,
        dc_req_latch: LatchIF,
        ic_serve_latch: LatchIF,
        dc_serve_latch: LatchIF,
        mem_backend: Mem,
        latency: int = 5,
        policy: str = "rr",
        max_inflight: int = 1,  # <= set to 1 for "no queueing" semantics
    ):
        self.name = name
        self.ic_req_latch = ic_req_latch
        self.dc_req_latch = dc_req_latch
        self.ic_serve_latch = ic_serve_latch
        self.dc_serve_latch = dc_serve_latch
        self.mem_backend = mem_backend

        self.latency = int(latency)
        self.policy = str(policy)
        self.max_inflight = int(max_inflight)

        # inflight requests being serviced by memory backend
        self.inflight: list[MemRequest] = []

        # RR toggle: 0 prefer I$, 1 prefer D$
        self.rr = 0

    # -----------------------------
    # Helpers
    # -----------------------------
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
            warpGroup=req_info.get("warpGroup", req_info.get("warp_group_id", None)),
            opcode=req_info.get("opcode", None),
            rs1=req_info.get("rs1", Bits(uint=0, length=5)),
            rs2=req_info.get("rs2", Bits(uint=0, length=5)),
            rd=req_info.get("rd", Bits(uint=0, length=5)),
        )

    # compatibility fix for naming conventions used across tests
    def _normalize_req(self, req: dict, src: str) -> dict:
        if not isinstance(req, dict):
            raise TypeError(f"[{self.name}] expected dict req, got {type(req)}")

        req = dict(req)  # copy
        req["src"] = src

        if "warp_id" not in req and "warp" in req:
            req["warp_id"] = req["warp"]
        if "warp_group_id" not in req and "warpGroup" in req:
            req["warp_group_id"] = req["warpGroup"]

        return req

    def _pick_from_inputs(self) -> Optional[dict]:
        """
        Choose one request directly from input latches (no internal request queues).
        IMPORTANT: Only call this when you are ready to accept and start service
        this cycle, because it POPs the chosen latch.
        """
        ic_valid = bool(self.ic_req_latch and self.ic_req_latch.valid)
        dc_valid = bool(self.dc_req_latch and self.dc_req_latch.valid)

        if not ic_valid and not dc_valid:
            return None

        if self.policy == "icache_prio":
            if ic_valid:
                raw = self.ic_req_latch.pop()
                return self._normalize_req(raw, "icache")
            raw = self.dc_req_latch.pop()
            return self._normalize_req(raw, "dcache")

        # Default: RR when both valid
        if ic_valid and dc_valid:
            if self.rr == 0:
                raw = self.ic_req_latch.pop()
                chosen = self._normalize_req(raw, "icache")
            else:
                raw = self.dc_req_latch.pop()
                chosen = self._normalize_req(raw, "dcache")
            self.rr ^= 1
            return chosen

        # Only one side valid
        if ic_valid:
            raw = self.ic_req_latch.pop()
            return self._normalize_req(raw, "icache")
        raw = self.dc_req_latch.pop()
        return self._normalize_req(raw, "dcache")

    def _try_start_one_request(self) -> None:
        """
        Start at most one new request per cycle.
        Backpressure is implemented by refusing to POP input latches when
        inflight capacity is full.
        """
        if len(self.inflight) >= self.max_inflight:
            return  # busy => do not pop => latch stays valid => upstream stalls

        req_info = self._pick_from_inputs()
        if req_info is None:
            return

        inst = req_info.get("inst", None) or self._build_min_inst(req_info)

        pc_int = inst.pc.int if isinstance(inst.pc, Bits) else int(inst.pc)
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

        mem_req.inst = inst
        mem_req.src = req_info.get("src", None)

        self.inflight.append(mem_req)

    def _age_inflight(self) -> None:
        for req in self.inflight:
            req.remaining -= 1

    def _complete_one_if_ready(self) -> None:
        """
        Complete at most one ready request (remaining <= 0) and push its response.
        If the corresponding response latch is not ready, we do NOT complete this cycle
        (keeps request inflight), which naturally backpressures completion.
        """
        for req in list(self.inflight):
            if req.remaining > 0:
                continue

            inst = getattr(req, "inst", None)
            src = getattr(req, "src", None)

            if src == "icache":
                if not self.ic_serve_latch.ready_for_push():
                    break
            elif src == "dcache":
                if not self.dc_serve_latch.ready_for_push():
                    break
            else:
                raise KeyError(f"[MemController] Missing/invalid src: {src}")

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
            else:
                data_bits = self.mem_backend.read(req.addr, req.size)
                resp = {
                    "src": src,
                    "rw_mode": "read",
                    "data": data_bits,
                    "addr": req.addr,
                    "size": req.size,
                    "uuid": req.uuid,
                    "warp": req.warp_id,
                    "pc": req.pc,
                    "inst": inst,
                }

            if src == "icache":
                self.ic_serve_latch.push(resp)
            elif src == "dcache":
                self.dc_serve_latch.push(resp)

            self.inflight.remove(req)
            break  # ONE completion per cycle

    # -----------------------------
    # Main compute
    # -----------------------------
    def compute(self, input_data=None):
        # 1) progress outstanding work
        self._age_inflight()

        # 2) complete at most one (if response latch allows)
        self._complete_one_if_ready()

        # 3) accept/start at most one new request, ONLY if capacity allows
        self._try_start_one_request()
