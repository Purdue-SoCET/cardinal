
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

        # # Timing / MSHR
        # self.mshr_limit = cache_config.get("mshr_entries", 8)

        # Set → list of cache lines
        self.cache = {i: [] for i in range(self.num_sets)}

        # Track outstanding misses
        # Each entry: {"block_addr", "set", "tag", "pc", "outstanding": True}
        # self.mshrs = []
        self.mem_req_if = mem_req_if
        self.mem_resp_if = mem_resp_if

        #----
        self.pending_fetch = None
        self.stalled = False 

        self.cycle = 0

    # # -------------- MSHR helpers ----------------
    # def _mshr_for_block(self, block_addr):
    #     for m in self.mshrs:
    #         if m["block_addr"] == block_addr:
    #             return m
    #     return None

    # def _allocate_mshr(self, pc: int):
    #     set_idx, tag, block_addr = self._addr_decode(pc)

    #     if len(self.mshrs) >= self.mshr_limit:
    #         return None  

    #     m = {
    #         "block_addr": block_addr,
    #         "set": set_idx,
    #         "tag": tag,
    #         "pc": pc,
    #         "outstanding": True
    #     }
    #     self.mshrs.append(m)
    #     return m

    # def _free_mshr(self, block_addr: int):
    #     self.mshrs = [m for m in self.mshrs if m["block_addr"] != block_addr]

    # -------------- Cache fill ----------------
    def _fill_cache_line(self, set_idx: int, tag: int, data_bits):
        ways = self.cache[set_idx]

        # Add new way if associative slots left
        if len(ways) < self.assoc:
            ways.append(ICacheEntry(tag, data_bits, valid=True))
            return

        # Otherwise, evict LRU
        victim = min(ways, key=lambda w: w.last_used)
        victim.tag = tag
        victim.data = data_bits
        victim.valid = True

    # -------------- Forward ihit --------------
    def _send_ihit(self, val: bool):
        if "ICache_Decode_Ihit" in self.forward_ifs_write:
            self.forward_ifs_write["ICache_Decode_Ihit"].push(val)
        
        ihit_forwarding_if = self.forward_ifs_write["ihit"] 
        if val == False:     
            ihit_forwarding_if.set_wait(True)
        else:
            ihit_forwarding_if.set_wait(False)
            
    def _addr_decode(self, pc):
        block = pc // self.block_size
        set_idx = block % self.num_sets
        tag = block // self.num_sets
        return set_idx, tag, block

    def _lookup(self, pc):
        set_idx, tag, _ = self._addr_decode(pc)
        print("Looking up the tag for:", set_idx, tag)
        for line in self.cache[set_idx]:
            if line.valid and line.tag == tag:
                line.last_used = self.cycle
                return line
        return None

    # -------------------------------------------
    # Fill cache line
    # -------------------------------------------
    def _fill(self, pc, data_bits):
        set_idx, tag, block = self._addr_decode(pc)
        ways = self.cache[set_idx]

        if len(ways) < self.assoc:
            ways.append(ICacheEntry(tag, data_bits))
        else:
            victim = min(ways, key=lambda w: w.last_used)
            victim.tag  = tag
            victim.data = data_bits
            victim.valid = True

        print(f"[ICache] FILL complete: PC=0x{pc:X}  → unblock + retry")


    # -------------------------------------------
    # Main compute
    # -------------------------------------------
    def compute(self, input_data=None):
        self.cycle += 1

        # =====================================================
        # STEP 1: Handle memory fill first
        # =====================================================
        if self.mem_resp_if.valid:
            resp = self.mem_resp_if.pop()
            pc = resp["pc"]
            data = resp["data"]

            print(f"[ICache] Received FILL for PC=0x{pc:X}")

            self._fill(pc, data)
            print(self.cache)
            # # freeing MSHR
            # _,_,block = self._addr_decode(pc)
            # self.mshrs = [m for m in self.mshrs if m["block_addr"] != block]

            # UNBLOCK
            self._send_ihit(True)
            self.stalled = False
            print("UNSTALLED AFTER A FILL!")
            # retry the stalled instruction next cycle
            if self.pending_fetch is not None:
                print("RETURN HERE!")
                # retry on next cycle
                return

        # =====================================================
        # STEP 2: If stalled → do NOT pop new request
        # =====================================================
        if self.stalled:
            print(f"[ICache] STALLED — waiting for fill, skipping pop")
            return

        # =====================================================
        # STEP 3: No request? nothing to do 
        # =====================================================
        if not self.behind_latch.valid:
            return

        req = self.behind_latch.snoop()
        pc  = req["pc"]

        # =====================================================
        # STEP 4: Lookup in cache
        # =====================================================
        hit_line = self._lookup(pc)
        print("GOT THIS FROM THE CACHE:", hit_line)
        if hit_line:
            self.behind_latch.pop()  # consume
            print(f"[ICache] HIT pc=0x{pc:X}")
            self._send_ihit(True)
            if self.ahead_latch.ready_for_push():
                self.ahead_latch.push({
                    "pc": pc,
                    "packet": hit_line.data
                })
            return

        # =====================================================
        # STEP 5: M I S S
        # =====================================================
        print(f"[ICache] MISS pc=0x{pc:X} → stall + memreq")

        # block pipeline here
        self._send_ihit(False)
        self.stalled = True
        self.pending_fetch = req  # save request for retry
        self.behind_latch.pop()

        # issue memory request only once
        set_idx,tag,block = self._addr_decode(pc)


        self.mem_req_if.push({
                "addr": block,
                "size": self.block_size,
                "uuid": block,
                "pc": pc
        })
        print(f"[ICache]   → MemReq sent for block=0x{block:X}")
        # else:
        #     print(f"[ICache]   → MSHR merge; no extra memreq")