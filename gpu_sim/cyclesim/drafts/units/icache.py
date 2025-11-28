
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

        # Cache geometry
        self.cache_size = cache_config.get("cache_size", 32 * 1024)
        self.block_size = cache_config.get("block_size", 64)
        self.assoc = cache_config.get("associativity", 4)
        self.num_sets = self.cache_size // (self.block_size * self.assoc)

        # Set → list of cache lines
        self.cache = {i: [] for i in range(self.num_sets)}

        self.mem_req_if = mem_req_if
        self.mem_resp_if = mem_resp_if

        self.pending_fetch: Optional[Instruction] = None
        self.stalled = False
        self.cycle = 0

    # ---------------- Cache line helpers ----------------
    def _fill_cache_line(self, set_idx: int, tag: int, data_bits):
        ways = self.cache[set_idx]
        if len(ways) < self.assoc:
            ways.append(ICacheEntry(tag, data_bits, valid=True))
        else:
            victim = min(ways, key=lambda w: w.last_used)
            victim.tag = tag
            victim.data = data_bits
            victim.valid = True

    def _send_ihit(self, val: bool):
        if "ICache_Decode_Ihit" in self.forward_ifs_write:
            self.forward_ifs_write["ICache_Decode_Ihit"].push(val)
        if "ihit" in self.forward_ifs_write:
            f_if = self.forward_ifs_write["ihit"]
            f_if.set_wait(not val)

    def _addr_decode(self, pc_int: int):
        block = pc_int // self.block_size
        set_idx = block % self.num_sets
        tag = block // self.num_sets
        return set_idx, tag, block

    def _lookup(self, pc_int: int):
        set_idx, tag, _ = self._addr_decode(pc_int)
        for line in self.cache[set_idx]:
            if line.valid and line.tag == tag:
                line.last_used = self.cycle
                return line
        return None

    def _fill(self, inst: Instruction, data_bits):
        pc_int = int(inst.pc)
        set_idx, tag, _ = self._addr_decode(pc_int)
        self._fill_cache_line(set_idx, tag, data_bits)
        print(f"[ICache] FILL complete: warp={inst.warp} group={inst.warpGroup} pc=0x{pc_int:X}")

    # ---------------- Main compute ----------------
    def compute(self, input_data=None):
        print(f"\n[ICache] cycle={self.cycle} stalled={self.stalled}")

        # STEP 1: Handle incoming memory response
        if self.mem_resp_if.valid:
            # MemStage now returns an Instruction, not a dict
            inst_from_mem: Instruction = self.mem_resp_if.pop()
            pc_int_resp = int(inst_from_mem.pc)
            print(f"[ICache] Received MemResp for warp={inst_from_mem.warp} "
                  f"group={inst_from_mem.warpGroup} pc=0x{pc_int_resp:X}")

            # data bits are in inst_from_mem.packet (set by MemStage)
            data_bits = inst_from_mem.packet
            if data_bits is None:
                print("[ICache] WARNING: MemResp Instruction has no packet data!")

            # Fill cache line for this PC
            self._fill(inst_from_mem, data_bits)

            # Unstall / notify scheduler
            self._send_ihit(True)
            self.stalled = False

            if self.pending_fetch:
                print(f"[ICache] RETRYING pending fetch for pc=0x{int(self.pending_fetch.pc):X}")
                # Scheduler will re-issue; we just return this cycle
                self.cycle += 1
                return

        # STEP 2: Stall check
        if self.stalled:
            print("[ICache] Still stalled, skipping new fetch")
            self.cycle += 1
            return

        # STEP 3: No new request
        if not self.behind_latch.valid:
            self.cycle += 1
            return

        # Instruction comes from scheduler / previous stage
        inst: Instruction = self.behind_latch.snoop()
        pc_int = int(inst.pc)

        # STEP 4: Lookup
        hit_line = self._lookup(pc_int)
        if hit_line:
            self.behind_latch.pop()
            print(f"[ICache] HIT warp={inst.warp} group={inst.warpGroup} pc=0x{pc_int:X}")
            self._send_ihit(True)

            # Update the Instruction's packet with cached data
            inst.packet = hit_line.data

            # Push the updated Instruction forward (not a dict)
            if self.ahead_latch.ready_for_push():
                self.ahead_latch.push(inst)

            self.cycle += 1
            return

        # STEP 5: MISS
        print(f"[ICache] MISS warp={inst.warp} group={inst.warpGroup} pc=0x{pc_int:X}")
        self._send_ihit(False)
        self.stalled = True
        self.pending_fetch = inst
        self.behind_latch.pop()

        set_idx, tag, block = self._addr_decode(pc_int)
        # Request includes the Instruction so MemStage can return it updated
        self.mem_req_if.push({
            "addr": block,
            "size": self.block_size,
            "uuid": block,
            "pc": pc_int,
            "inst": inst,
        })
        print(f"[ICache] → MemReq issued for block=0x{block:X}, warp={inst.warp}, group={inst.warpGroup}")
        self.cycle += 1
        return