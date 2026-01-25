from base import ForwardingIF, LatchIF, Stage, Instruction, ICacheEntry, MemRequest, FetchRequest, DecodeType
from Memory import Mem
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from collections import deque
from datetime import datetime
from isa_packets import ISA_PACKETS
from bitstring import Bits 
global_cycle = 0

# SETTING THE LATCHES 

FetchICacheIF = LatchIF(name="Fetch_ICache_IF")
ICacheDecodeIF = LatchIF(name = "ICacheDecodeIF")
ICacheMemReqIF = LatchIF(name="ICacheMemReqIF")
MemICacheRespIF = LatchIF(name="MemICacheRespIF")
DecodeIssue_IbufferIF = LatchIF(name = "DecodeIIF")  

de_scheds = ForwardingIF(name = "Decode_Scheduler_Signals")
icache_de_ihit = ForwardingIF(name = "ICache_Decode_Ihit")


class BranchFU:
    def __init__(self, instructions: Instruction, prf_rd_data, op_1, op_2):
        self.warp_id = instructions.warp
        self.decode_mapping_table = {
            0: "beq",
            1: "bne",
            2: "bge",
            3: "bgeu",
            4: "blt",
            5: "bltu",
        }
        self.opcode = self.decode_mapping_table[instructions.opcode]
        self.prf_rd_data = prf_rd_data
        self.op1 = op_1
        self.op2 = op_2
        self.num_threads = len(op_1)
        self.prf_wr_data = None

    def to_signed(self, val, bits=32):
        if val & (1 << (bits - 1)):
            val -= 1 << bits
        return val

    def alu_decoder(self):
        if self.opcode == "beq":
            results = [self.op1[i] == self.op2[i] for i in range(self.num_threads)]
        elif self.opcode == "bne":
            results = [self.op1[i] != self.op2[i] for i in range(self.num_threads)]
        elif self.opcode == "bge":
            results = [self.to_signed(self.op1[i]) >= self.to_signed(self.op2[i]) for i in range(self.num_threads)]
        elif self.opcode == "bgeu":
            results = [self.op1[i] >= self.op2[i] for i in range(self.num_threads)]
        elif self.opcode == "blt":
            results = [self.to_signed(self.op1[i]) < self.to_signed(self.op2[i]) for i in range(self.num_threads)]
        elif self.opcode == "bltu":
            results = [self.op1[i] < self.op2[i] for i in range(self.num_threads)]
        else:
            raise ValueError(f"Unknown opcode {self.opcode}")
        return results

    def update_pred(self):
        tnt = self.alu_decoder()
        self.prf_wr_data = [
            self.prf_rd_data[i] and tnt[i] for i in range(self.num_threads)
        ]
        return self.prf_wr_data
 
class PredicateRegFile():
    def __init__(self, num_preds_per_warp: int, num_warps: int):
        num_cols = num_preds_per_warp *2 # the number of 
        self.num_threads = 32

        # 2D structure: warp -> predicate -> [bits per thread]
        self.reg_file = [
            [[[False] * self.num_threads, [False] * self.num_threads]
              for _ in range(num_cols)]
            for _ in range(num_warps)
        ]
    
    def read_predicate(self, prf_rd_en: int, prf_rd_wsel: int, prf_rd_psel: int, prf_neg: int):
        "Predicate register file reads by selecting a 1 from 32 warps, 1 from 16 predicates,"
        " and whether it wants the inverted version or not..."

        if (prf_rd_en):
            return self.reg_file[prf_rd_wsel][prf_rd_psel][prf_neg]
        else: 
            return None
    
    def write_predicate(self, prf_wr_en: int, prf_wr_wsel: int, prf_wr_psel: int, prf_wr_data):
        # the write will autopopulate the negated version in the table)
        if (prf_wr_en):
                # Convert int to bit array if needed
            if isinstance(prf_wr_data, int):
                bits = [(prf_wr_data >> i) & 1 == 1 for i in range(self.num_threads)]
            else:
                bits = prf_wr_data  # assume already a list of bools

            # Store positive version
            self.reg_file[prf_wr_wsel][prf_wr_psel][0] = bits
            # Store negated version
            self.reg_file[prf_wr_wsel][prf_wr_psel][1] = [not b for b in bits]


class FetchStage(Stage):
    """
    FetchStage: drives PC fetch requests into the ICache.
    Uses Bits placeholders and supports non-blocking instruction requests.
    """

    def __init__(
        self,
        name: str,
        behind_latch: Optional[LatchIF],
        ahead_latch: Optional[LatchIF],
        start_pc: int = 0x1000,
        warp_id: int = 0,
        next_pc_stride: int = 0x4,
    ):
        super().__init__(name=name, behind_latch=behind_latch, ahead_latch=ahead_latch)
        self.pc = start_pc
        self.warp_id = warp_id
        self.next_pc_stride = next_pc_stride
        self.active = True

    def compute(self, input_data: Optional[Any] = None) -> None:
        """
        Called each cycle to generate a fetch request for the next PC.
        Sends a FetchRequest through ahead_latch if ready.
        """
        if not self.active:
            print(f"[{self.name}] Idle (no more fetches).")
            return None

        if not self.ahead_latch.ready_for_push():
            print(f"[{self.name}] Stall — next stage not ready.")
            return None

        # Build the fetch request payload
        req = FetchRequest(
            pc=self.pc,
            warp_id=self.warp_id,
            uuid=self.pc,  # could later become an instruction ID
        )

        # Optionally include an empty Bits packet placeholder
        # (can be useful if later stages expect 'packet' field)
        packet_placeholder = Bits(uint=0, length=32)
        payload = {"pc": self.pc, "warp": self.warp_id, "uuid": self.pc, "packet": packet_placeholder}

        # Push request to next stage
        pushed = self.ahead_latch.push(payload)
        if pushed:
            print(f"[{self.name}] Fetch issued PC=0x{self.pc:X} → ICache")
            # Advance to next PC
            self.pc += self.next_pc_stride
        else:
            print(f"[{self.name}] Could not push — latch busy.")

        return None

class MemStage(Stage):
    """Memory controller functional unit using Mem() backend."""

    def __init__(
        self,
        name: str,
        behind_latch: Optional[LatchIF],
        ahead_latch: Optional[LatchIF],
        mem_backend,                 # <-- existing Mem class instance
        latency: int = 100,
    ):
        super().__init__(name=name, behind_latch=behind_latch, ahead_latch=ahead_latch)
        self.mem_backend = mem_backend
        self.latency = latency
        self.inflight: list[MemRequest] = []

    def compute(self, input_data: Optional[Any] = None):
        # Progress all inflight requests
        completed = []
        for req in self.inflight:
            req.remaining -= 1
            if req.remaining <= 0:
                data = self.mem_backend.read(req.addr, req.size)
                if self.ahead_latch.ready_for_push():
                    self.ahead_latch.push({
                        "uuid": req.uuid,
                        "data": data,
                        "warp": req.warp_id
                    })
                    print(f"[{self.name}] Completed read @0x{req.addr:X}")
                completed.append(req)
        for c in completed:
            self.inflight.remove(c)

        # --- Accept new requests ---
        if self.behind_latch and self.behind_latch.valid:
            req_info = self.behind_latch.pop()
            mem_req = MemRequest(
                addr=req_info["addr"],
                size=req_info.get("size", 4),
                uuid=req_info.get("uuid", 0),
                warp_id=req_info.get("warp", 0),
                remaining=self.latency,
            )
            self.inflight.append(mem_req)
            print(f"[{self.name}] Accepted mem req @0x{mem_req.addr:X} lat={self.latency}")

class ICacheStage(Stage):
    def __init__(
        self,
        name: str,
        behind_latch: Optional[LatchIF],
        ahead_latch: Optional[LatchIF],
        mem_req_if,
        mem_resp_if,
        cache_config: Dict[str, int],
        forward_ifs_write: Optional[Dict[str, ForwardingIF]] = None,
    ):
        super().__init__(
            name=name,
            behind_latch=behind_latch,
            ahead_latch=ahead_latch,
            forward_ifs_write=forward_ifs_write or {},
        )
        self.cache_size = cache_config.get("cache_size", 32 * 1024)
        self.block_size = cache_config.get("block_size", 64)
        self.assoc = cache_config.get("associativity", 4)
        self.num_sets = self.cache_size // (self.block_size * self.assoc)
        self.miss_latency = cache_config.get("miss_latency", 5)
        self.mshr_limit = cache_config.get("mshr_entries", 8)
        self.cache: Dict[int, List[ICacheEntry]] = {i: [] for i in range(self.num_sets)}
        self.pending_misses: List[Dict[str, Any]] = []
        self.mem_req_if = mem_req_if
        self.mem_resp_if = mem_resp_if
        self.cycle_count = 0

    # ---------- helper methods ----------
    def _get_set_tag(self, pc):
        block_addr = pc // self.block_size
        set_idx = block_addr % self.num_sets
        tag = block_addr // self.num_sets
        return set_idx, tag, block_addr

    def _lookup(self, pc):
        set_idx, tag, _ = self._get_set_tag(pc)
        for line in self.cache[set_idx]:
            if line.valid and line.tag == tag:
                line.last_used = self.cycle_count
                return line
        return None

    def _fill_cache_line(self, set_idx, tag, data):
        ways = self.cache[set_idx]
        if len(ways) < self.assoc:
            ways.append(ICacheEntry(tag, data))
        else:
            victim = min(ways, key=lambda w: w.last_used)
            victim.tag, victim.data, victim.valid = tag, data, True

    def _send_ihit(self, ihit: bool):
        if "ICache_Decode_Ihit" in self.forward_ifs_write:
            self.forward_ifs_write["ICache_Decode_Ihit"].push(ihit)

    # ---------- main per-cycle logic ----------
    def compute(self, input_data: Optional[Any] = None):
        self.cycle_count += 1

        # --- 1. Handle completed memory responses ---
        if self.mem_resp_if.valid:
            resp = self.mem_resp_if.pop()
            block_addr = resp["uuid"]
            set_idx, tag, _ = self._get_set_tag(block_addr)
            data_bits = resp["data"]
            self._fill_cache_line(set_idx, tag, data_bits)
            print(f"[{self.name}] Filled cache line for block 0x{block_addr:X}")

        # --- 2. Handle new fetch request ---
        if not self.behind_latch.valid:
            return None

        req = self.behind_latch.pop()
        pc = req["pc"]
        set_idx, tag, block_addr = self._get_set_tag(pc)
        line = self._lookup(pc)

        if line:
            self._send_ihit(True)
            if self.ahead_latch.ready_for_push():
                self.ahead_latch.push({"pc": pc, "packet": line.data})
            print(f"[{self.name}] Hit @ PC=0x{pc:X}")
        else:
            self._send_ihit(False)
            if len(self.pending_misses) < self.mshr_limit and self.mem_req_if.ready_for_push():
                self.mem_req_if.push({"addr": block_addr, "size": self.block_size, "uuid": block_addr})
                print(f"[{self.name}] Miss @0x{pc:X} → Sent MemReq block=0x{block_addr:X}")
            else:
                print(f"[{self.name}] Stall (MSHR full or MemReq not ready)")

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

    def compute(self, input_data: Optional[Any] = None):
        """Decode the raw instruction word coming from behind_latch."""
        if input_data is None:
            return None

        inst = input_data

        # Stall if any read-forwarding interface is waiting
        for fwd_if in self.forward_ifs_read.values():
            if fwd_if.wait:
                print(f"[{self.name}] Stalled due to wait from next stage.")
                return None

        # Gather any valid forwarded signals (like ICache ihit)
        fwd_values = {
            name: f.pop() for name, f in self.forward_ifs_read.items() if f.payload is not None
        }

        if "ICache_Decode_Ihit" in fwd_values and not fwd_values["ICache_Decode_Ihit"]:
            print(f"[{self.name}] Waiting on ICache ihit signal...")
            return None

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
            raw = sum((byte & 0xFF) << (8 * i) for i, byte in enumerate(raw_field[:4])) & 0xFFFFFFFF
        else:
            raise TypeError(f"[{self.name}] Unsupported packet type: {type(raw_field)}")

        # === Decode bitfields ===
        opcode7 = raw & 0x7F
        rd = (raw >> 7) & 0x3F
        rs1 = (raw >> 13) & 0x3F
        mid6 = (raw >> 19) & 0x3F
        pred = (raw >> 25) & 0x1F
        packet_start = bool((raw >> 30) & 0x1)
        packet_end = bool((raw >> 31) & 0x1)

        opcode_map = {
            0b0000000: "add",  0b0000001: "sub",  0b0000010: "mul",
            0b0000011: "div",  0b0100000: "lw",   0b0110000: "sw",
            0b1000000: "beq",  0b1100000: "jal",  0b1111111: "halt",
        }

        mnemonic = opcode_map.get(opcode7, "nop")

        inst.opcode = mnemonic
        inst.rs1 = rs1
        inst.rs2 = mid6
        inst.rd = rd
        
        decode_flags = DecodeType(
            halt=(opcode7 == 0b1111111),
            EOP=bool((raw >> 31) & 0x1),              # End-of-packet bit
            MOP=bool((raw >> 30) & 0x1),              # Multi-op bit (example)
            Barrier=bool((raw >> 29) & 0x1)           # Barrier bit (example)
        )

        inst.type = decode_flags  # attach decoded type to instruction

        # === Forward to next stage ===
        for name, f in self.forward_ifs_write.items():
            f.push({"decoded": True, "type": decode_flags, "pc": self.pc})
        # @daniel_yang 
            # check this part daniel

        pred_mask = self.prf.read_predicate(
            prf_rd_en=1, prf_rd_wsel=inst.warp, prf_rd_psel=pred, prf_neg=0
        )
        inst.pred = pred_mask or [True] * 32


        print(
            f"[{self.name}] Decoded opcode={mnemonic}, rs1={rs1}, rs2={mid6}, rd={rd}, "
            f"pred[0]={inst.pred[0] if inst.pred else None}"
        )
        # === Timing Bookkeeping ===
        from datetime import datetime
        
        global global_cycle
        inst.stage_entry.setdefault("Decode", global_cycle)
        inst.stage_exit["Decode"] = global_cycle + 1
        inst.issued_cycle = inst.issued_cycle or global_cycle

        self.send_output(inst)
        return inst


## TEST INIT CODE BELOW ##

# --- Prerequisites ---
# Assuming DecodeStage, Instruction, PredicateRegFile, LatchIF, ForwardingIF are all imported

def make_test_pipeline():
    """Helper to build a test decode stage pipeline setup."""
    mem_backend = Mem(start_pc=0x1000, \
    input_file="/home/shay/a/sing1018/Desktop/SoCET_GPU_FuncSim/gpu/gpu_sim/cyclesim/drafts/test.bin",
    fmt="bin")
    prf = PredicateRegFile(num_preds_per_warp=16, num_warps=32)
    cache_cfg = {
        "cache_size": 32 * 32,
        "block_size": 32,
        "associativity": 1,
        "miss_latency": 5,
        "mshr_entries": 4,
    }
    # Preload predicate registers for warp 0
    prf.write_predicate(prf_wr_en=1, prf_wr_wsel=0, prf_wr_psel=0,
                        prf_wr_data=[True, False] * 16)

    inst = Instruction(iid=1, pc=0x100, warp=0, warpGroup=0,
                       opcode=0, rs1=0, rs2=0, rd=0, pred=0, packet=None)
        # Build DecodeStage fully compatible with Stage
    fetch_stage = FetchStage(name="Fetch", 
                             behind_latch=None,
                             ahead_latch=FetchICacheIF
                            )
    icache_stage = ICacheStage(name = "ICache",
                               behind_latch=FetchICacheIF,
                               ahead_latch=ICacheDecodeIF,
                               mem_req_if=ICacheMemReqIF,
                               mem_resp_if=MemICacheRespIF,
                            #    backend=mem_backend,
                               cache_config=cache_cfg,
                               forward_ifs_write={"ihit": icache_de_ihit}
                               )
    
    mem_stage = MemStage(
        name = "Memory",
        behind_latch=ICacheMemReqIF,
        ahead_latch=MemICacheRespIF,
        mem_backend=mem_backend,
        latency=50
    )

    decode_stage = DecodeStage(
        name="Decode",
        prf=prf, 
        behind_latch=ICacheDecodeIF,
        ahead_latch=DecodeIssue_IbufferIF,
        forward_ifs_read={"ICache_Decode_Ihit": icache_de_ihit},
        forward_ifs_write={
            "Decode_Scheduler_EOP": de_scheds
        }
    )

    for latch in [
        FetchICacheIF, ICacheDecodeIF,
        ICacheMemReqIF, MemICacheRespIF,
        DecodeIssue_IbufferIF
    ]:
        latch.clear_all()

    return {
        "fetch": fetch_stage,
        "icache": icache_stage,
        "mem": mem_stage,
        "decode": decode_stage,
        "mem_backend": mem_backend,
        "latches": {
            "fetch_icache": FetchICacheIF,
            "icache_decode": ICacheDecodeIF,
            "icache_memreq": ICacheMemReqIF,
            "mem_icache": MemICacheRespIF,
            "decode_issue": DecodeIssue_IbufferIF
        },
        "fwd_ifs": {
            "ihit": icache_de_ihit
        },
        "prf": prf
    }

if __name__ == "__main__":
    sim = make_test_pipeline()
    fetch = sim["fetch"]
    icache = sim["icache"]
    mem = sim["mem"]
    decode = sim["decode"]

    for cycle in range(20):
        print(f"\n=== Cycle {cycle} ===")

        # Snapshot latch states before compute
        prev_payloads = {name: (l.payload, l.valid) for name, l in sim["latches"].items()}

        # Compute all stages
        fetch.compute()
        icache.compute()
        mem.compute()
        decode.compute()

        # Restore previous payloads (so next stage only sees updates next cycle)
        for name, latch in sim["latches"].items():
            latch.prev_payload, latch.prev_valid = prev_payloads[name]
            latch.payload, latch.valid = latch.prev_payload, latch.prev_valid


