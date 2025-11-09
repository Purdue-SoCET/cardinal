from base import ForwardingIF, LatchIF, Stage, Instruction, ICacheEntry
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from collections import deque
from datetime import datetime
from isa_packets import ISA_PACKETS

global_cycle = 0


FetchICacheIF = LatchIF(name="Fetch_ICache_IF")
ICacheDecodeIF = LatchIF(name = "ICacheDecodeIF")
DecodeIssue_IbufferIF = LatchIF(name = "DecodeIIF")  
de_sched_EOP = ForwardingIF(name = "Decode_Scheduler_EOP")
de_sched_EOP_WID = ForwardingIF(name = "Decode_Scheduler_WARPID")
de_sched_BARR = ForwardingIF(name = "Deecode_Schedular_BARRIER")
de_sched_B_WID = ForwardingIF(name = "Decode_Scheduler_BARRIER_WARPID")
de_sched_B_GID = ForwardingIF(name = "Decode_Scheduler_BARRIER_GROUPID")
de_sched_B_PC = ForwardingIF(name = "Decode_Scheduler_BARRIER_PC")
icache_de_ihit = ForwardingIF(name = "ICache_Decode_Ihit")

# @dataclass
# class FU():
#     name = 
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

class ICacheStage(Stage):
 def __init__(
        self,
        name: str,
        behind_latch: Optional[LatchIF],
        ahead_latch: Optional[LatchIF],
        backend,
        cache_config: Dict[str, int],
        forward_ifs_write: Optional[Dict[str, ForwardingIF]] = None,
    ):
        super().__init__(
            name=name,
            behind_latch=behind_latch,
            ahead_latch=ahead_latch,
            forward_ifs_write=forward_ifs_write or {},
        )

        # --- Core config ---
        self.cache_size = cache_config.get("cache_size", 32 * 1024)
        self.block_size = cache_config.get("block_size", 64)
        self.assoc = cache_config.get("associativity", 4)
        self.miss_latency = cache_config.get("miss_latency", 5)
        self.num_sets = self.cache_size // (self.block_size * self.assoc)

        # --- State ---
        self.cache: Dict[int, List[ICacheEntry]] = {
            s: [] for s in range(self.num_sets)
        }
        self.backend = backend
        self.pending_misses: List[Dict[str, Any]] = []
        self.mshr_limit = cache_config.get("mshr_entries", 8)
        self.cycle_count = 0

# ----------------------------------------------------------------------
def _get_set_and_tag(self, pc: int):
    block_addr = pc // self.block_size
    set_idx = block_addr % self.num_sets
    tag = block_addr // self.num_sets
    return set_idx, tag, block_addr

def _lookup(self, pc: int):
    set_idx, tag, block_addr = self._get_set_and_tag(pc)
    way_list = self.cache[set_idx]
    for way in way_list:
        if way.valid and way.tag == tag:
            way.last_used = self.cycle_count
            return way
    return None

def _fill_cache_line(self, set_idx: int, tag: int, data: bytes):
    ways = self.cache[set_idx]
    if len(ways) < self.assoc:
        ways.append(ICacheEntry(tag, data))
    else:
        victim = min(ways, key=lambda w: w.last_used)
        victim.tag = tag
        victim.data = data
        victim.valid = True
        victim.last_used = self.cycle_count

# ----------------------------------------------------------------------
def compute(self, input_data: Any):
    """
    Called once per global pipeline tick.
    1. Progress outstanding misses
    2. Handle new fetch requests
    3. Send ihit forward and instruction to next stage
    """
    self.cycle_count += 1

    # --- 1. Progress outstanding misses ---
    finished = []
    for miss in self.pending_misses:
        miss["remaining"] -= 1
        if miss["remaining"] == 0:
            data = self.backend.read_block(miss["block_addr"], self.block_size)
            self._fill_cache_line(miss["set_idx"], miss["tag"], data)
            self._send_hit_signal(True)
            # return fetched instruction
            if self.ahead_latch.ready_for_push():
                self.ahead_latch.push({"pc": miss["pc"], "packet": data})
            finished.append(miss)
    for m in finished:
        self.pending_misses.remove(m)

    # --- 2. Handle new fetch request ---
    if input_data is None:
        return None

    pc = input_data.pc
    entry = self._lookup(pc)
    set_idx, tag, block_addr = self._get_set_and_tag(pc)

    if entry is not None:
        # Cache hit
        self._send_hit_signal(True)
        if self.ahead_latch.ready_for_push():
            self.ahead_latch.push({"pc": pc, "packet": entry.data})
        print(f"[{self.name}] ICache hit @ PC=0x{pc:X}")
    else:
        # Cache miss
        self._send_hit_signal(False)
        print(f"[{self.name}] ICache miss @ PC=0x{pc:X} → issuing memory read")

        if len(self.pending_misses) < self.mshr_limit:
            self.pending_misses.append({
                "pc": pc,
                "tag": tag,
                "set_idx": set_idx,
                "block_addr": block_addr,
                "remaining": self.miss_latency,
            })
        else:
            print(f"[{self.name}] MSHR full, stalling fetch.")

    return None

# ----------------------------------------------------------------------
def _send_hit_signal(self, ihit: bool):
    """Send a signal to Decode through ForwardingIF."""
    if "ICache_Decode_Ihit" in self.forward_ifs_write:
        self.forward_ifs_write["ICache_Decode_Ihit"].push(ihit)

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

    def compute(self, input_data: Any) -> Optional[Instruction]:
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
        if isinstance(raw_field, str):
            raw = int(raw_field, 0) & 0xFFFFFFFF
        elif isinstance(raw_field, list):
            raw = 0
            for i, byte in enumerate(raw_field):
                raw |= (byte & 0xFF) << (8 * i)
            raw &= 0xFFFFFFFF
        else:
            raw = int(raw_field) & 0xFFFFFFFF

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
        # inst.packet_start = packet_start
        # inst.packet_end = packet_end

        pred_mask = self.prf.read_predicate(
            prf_rd_en=1, prf_rd_wsel=inst.warp, prf_rd_psel=pred, prf_neg=0
        )
        inst.pred = pred_mask or [True] * 32

        # Send forward signals
        for name, f in self.forward_ifs_write.items():
            f.push({"decoded": True, "warp": inst.warp, "pc": inst.pc})

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
    prf = PredicateRegFile(num_preds_per_warp=16, num_warps=32)
    
    # Preload predicate registers for warp 0
    prf.write_predicate(prf_wr_en=1, prf_wr_wsel=0, prf_wr_psel=0,
                        prf_wr_data=[True, False] * 16)

    inst = Instruction(iid=1, pc=0x100, warp=0, warpGroup=0,
                       opcode=0, rs1=0, rs2=0, rd=0, pred=0, packet=None)
        # Build DecodeStage fully compatible with Stage
    decode_stage = DecodeStage(
        name="Decode",
        prf=prf, 
        behind_latch=FetchDecodeIF,
        ahead_latch=DecodeIssue_IbufferIF,
        forward_ifs_read={"ICache_Decode_Ihit": icache_de_ihit},
        forward_ifs_write={
            "Decode_Scheduler_EOP": de_sched_EOP,
            "Decode_Scheduler_EOP_WARPID": de_sched_EOP_WID,
            "Decode_Schedular_BARRIER": de_sched_BARR,
            "Decode_Scheduler_BARRIER_WARPID": de_sched_B_WID,
            "Decode_Scheduler_BARRIER_GROUPID": de_sched_B_GID,
            "Decode_Scheduler_BARRIER_PC": de_sched_B_PC,
        }
    )
    FetchDecodeIF.clear_all()
    DecodeIssue_IbufferIF.clear_all()

    return decode_stage, inst, prf


def test_rtype_instruction():
    decode, inst, prf = make_test_pipeline()

    inst.packet = "0x0000190D89"
    FetchDecodeIF.force_push(inst)
    global global_cycle
    print(f"\n=== Cycle {global_cycle} ===")
    decode.compute(FetchDecodeIF.pop())
    global_cycle += 1

    decoded_out = DecodeIssue_IbufferIF.pop()
    assert decoded_out is not None
    print("[R-Type] Decoded:", decoded_out)

def test_load_instruction():
    decode, inst, prf = make_test_pipeline()
    inst.packet = "0x0200112090"  # lw-like
    FetchDecodeIF.force_push(inst)
    decode.step()
    decoded_out = DecodeIssue_IbufferIF.pop()
    assert decoded_out.opcode != 0
    assert decoded_out.rs1 == (int("0x0200112090", 16) >> 13) & 0x3F
    print("[I-Type Load] Decoded:", decoded_out)


def test_store_instruction():
    decode, inst, prf = make_test_pipeline()
    inst.packet = "0x03001928C0"  # sw-like
    FetchDecodeIF.force_push(inst)
    decode.step()
    decoded_out = DecodeIssue_IbufferIF.pop()
    print("[S-Type Store] Decoded:", decoded_out)
    assert decoded_out.rs1 != 0
    assert decoded_out.rs2 != 0


def test_branch_instruction():
    decode, inst, prf = make_test_pipeline()
    inst.packet = "0x0800190980"  # beq-like
    FetchDecodeIF.force_push(inst)
    decode.step()
    decoded_out = DecodeIssue_IbufferIF.pop()
    print("[B-Type Branch] Decoded:", decoded_out)
    assert decoded_out.opcode != 0
    assert isinstance(decoded_out.pred, list)


def test_jump_instruction():
    decode, inst, prf = make_test_pipeline()
    inst.packet = "0x0C00080900"  # jal-like
    FetchDecodeIF.force_push(inst)
    decode.step()
    decoded_out = DecodeIssue_IbufferIF.pop()
    print("[J-Type Jump] Decoded:", decoded_out)
    assert decoded_out.opcode != 0
    assert decoded_out.rd != 0

def test_wait_on_ihit_false():
    decode, inst, prf = make_test_pipeline()

    # Simulate ICache miss (ihit=False)
    icache_de_ihit.push(False)

    inst.packet = "0x0000190D89"
    FetchDecodeIF.force_push(inst)
    decode.compute(FetchDecodeIF.pop())
    global global_cycle
    global_cycle +=1

    # Decode should stall → not push to next stage
    assert not DecodeIssue_IbufferIF.valid
    print("[ForwardIF] Correctly stalled on ihit=False")


def test_ready_on_ihit_true():
    decode, inst, prf = make_test_pipeline()

    icache_de_ihit.push(True)  # ihit=True
    inst.packet = "0x0000190D89"
    global global_cycle
    FetchDecodeIF.force_push(inst)
    decode.compute(FetchDecodeIF.pop())
    global_cycle +=1

    # Should have forwarded decode result
    assert DecodeIssue_IbufferIF.valid
    print("[ForwardIF] Correctly forwarded on ihit=True")

def test_multiple_back_to_back_instructions():
    global global_cycle
    global_cycle = 0

    decode, inst, prf = make_test_pipeline()

    # 3 back-to-back packets (different raw encodings)
    packets = [
        "0x0000190D89",  # add-like
        "0x0200112090",  # lw-like
        "0x0800190980",  # beq-like
    ]

    print("\n=== Simulating multiple back-to-back instructions ===")

    # feed one packet per cycle
    for pkt in packets:
        inst.packet = pkt
        FetchDecodeIF.force_push(inst)
        print(f"\n--- Cycle {global_cycle} ---")
        decode.compute(FetchDecodeIF.pop())
        global_cycle += 1

        decoded_out = DecodeIssue_IbufferIF.pop()
        if decoded_out:
            print(f"[Cycle {global_cycle}] Forwarded: opcode={decoded_out.opcode}, "
                  f"entry={decoded_out.stage_entry}, exit={decoded_out.stage_exit}")
        else:
            print(f"[Cycle {global_cycle}] No valid output this cycle.")

    print("\n✅ Back-to-back simulation complete.")

def test_set_outgoing_wait_and_clear():
    decode, inst, prf = make_test_pipeline()
    decode.set_outgoing_wait()
    assert any(f.wait for f in decode.outgoing_ifs)
    decode.clear_outgoing()
    assert all(not f.wait and not f.valid for f in decode.outgoing_ifs)
    print("[ForwardIF] Wait/Clear verified")

def test_branch_fu_updates_predicate():
    print("\n=== BranchFU → Predicate Interaction Test ===")

    # Setup decode pipeline and predicate register file
    decode, inst, prf = make_test_pipeline()
    warp_id = 0
    pred_index = 0  # test first predicate slot

    # Preload alternating predicate values
    initial_mask = [True if i % 2 == 0 else False for i in range(32)]
    prf.write_predicate(prf_wr_en=1, prf_wr_wsel=warp_id,
                        prf_wr_psel=pred_index, prf_wr_data=initial_mask)

    # === Cycle 0: Decode a branch instruction ===
    inst.packet = ISA_PACKETS["beq"]
    FetchDecodeIF.force_push(inst)
    decoded_inst = decode.compute(FetchDecodeIF.pop())

    # Inputs for BranchFU (simulate operands)
    op1 = [10] * 32
    op2 = [10] * 32  # equal → taken branch
    prf_rd_data = prf.read_predicate(1, warp_id, pred_index, 0)

    branch_fu = BranchFU(decoded_inst, prf_rd_data, op1, op2)
    new_mask = branch_fu.update_pred()

    # Write result back to predicate register file
    prf.write_predicate(1, warp_id, pred_index, new_mask)

    print(f"[BranchFU] Updated predicate mask[0:8]: {new_mask[:8]}")

    # === Cycle 1: Decode another instruction (add) that uses same warp/predicate ===
    next_inst = Instruction(iid=2, pc=0x104, warp=warp_id, warpGroup=0,
                            opcode=0, rs1=0, rs2=0, rd=0, pred=pred_index,
                            packet=ISA_PACKETS["add"])
    FetchDecodeIF.force_push(next_inst)
    decoded_next = decode.compute(FetchDecodeIF.pop())

    print(f"[Decode] Post-branch predicate mask[0:8]: {decoded_next.pred[:8]}")

    # === Assertions ===
    assert decoded_next is not None
    assert decoded_next.pred != initial_mask, "Predicate mask did not update!"
    assert all(decoded_next.pred), "Expected all True after beq taken"
    print("✅ BranchFU predicate update successfully propagated.")

if __name__ == "__main__":
    test_rtype_instruction()
    test_multiple_back_to_back_instructions()
    test_wait_on_ihit_false()
    test_ready_on_ihit_true()
    print("\n✅ All DecodeStage tests passed.")
