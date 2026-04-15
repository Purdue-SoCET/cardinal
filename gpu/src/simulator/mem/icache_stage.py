
import sys
from pathlib import Path

parent_dir = Path(__file__).resolve().parents[3]
sys.path.append(str(parent_dir))

from simulator.interfaces import ForwardingIF, LatchIF
from simulator.stage import Stage
from simulator.instruction import Instruction
from simulator.mem_types import ICacheEntry, MemRequest, FetchRequest, DecodeType
from simulator.mem.memory import Mem
from simulator.utils.performance_counter.cache import CachePerfCount
from simulator.utils.performance_counter.telemeter import Telemeter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from collections import deque
from datetime import datetime
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
        telemeter: Optional[Telemeter] = None,
    ):
        super().__init__(
            name=name,
            behind_latch=behind_latch,
            ahead_latch=ahead_latch,
            forward_ifs_write=forward_ifs_write or {},
        )

        self.perf_count = CachePerfCount(name=name)
        if telemeter is not None:
            telemeter.register_unit(self.perf_count)

        # Cache geometry
        self.cache_size = cache_config.get("cache_size", 32 * 1024)
        self.block_size = cache_config.get("block_size", 64)
        self.assoc = cache_config.get("associativity", 4)
        self.num_sets = self.cache_size // (self.block_size * self.assoc)

        self.cache = {i: [] for i in range(self.num_sets)}

        self.mem_req_if = mem_req_if
        self.mem_resp_if = mem_resp_if
        self.req: Dict
        self.req_latched = False

        self.pending = False
        self.pending_fetch: Optional[Instruction] = None
        self.stalled = False
        self.cycle = 0

    # ---------------- Cache helpers ----------------
    def _fill_cache_line(self, set_idx: int, tag: int, data_bits):
        ways = self.cache[set_idx]
        if len(ways) < self.assoc:
            ways.append(ICacheEntry(tag, data_bits, valid=True))
        else:
            victim = min(ways, key=lambda w: w.last_used)
            victim.tag = tag
            victim.data = data_bits
            victim.valid = True

    # sending ready/stalled signals to scheduler
    def _send_valid(self, val: bool, eop: bool, warp_id: int):
        self.forward_ifs_write["ICache_Scheduler"].push({"fetch": val, "eop": eop, "warp_id": warp_id})
        # if "ICache_scheduler_Ihit" in self.forward_ifs_write:
        #     self.forward_ifs_write["ICache_scheduler_Ihit"].push(val)
        # if "ihit" in self.forward_ifs_write:
        #     self.forward_ifs_write["ihit"].set_wait(not val)

    # decoding address
    def _addr_decode(self, pc_int: int):
        block = pc_int // self.block_size
        set_idx = block % self.num_sets
        tag = block // self.num_sets
        return set_idx, tag, block

    # lookup pc from the I$
    def _lookup(self, pc_int: int):
        set_idx, tag, _ = self._addr_decode(pc_int)
        for line in self.cache[set_idx]:
            if line.valid and line.tag == tag:
                line.last_used = self.cycle
                return line
        return None

    # putting into I$
    def _fill_from_response(self, pc_int: int, data_bits):
        set_idx, tag, _ = self._addr_decode(pc_int)
        self._fill_cache_line(set_idx, tag, data_bits)
        # print(f"[I    Cache] FILL complete: pc=0x{pc_int:X}")

    # ---------------- Main compute ----------------
    def compute(self):
        # Perf counter signals for this cycle
        _is_hit = False
        _is_miss = False
        _is_busy = False
        _is_stalled = False

        # req in flight to memory
        if self.pending:
            _is_busy = True
            # memory returns value
            if self.mem_resp_if.valid:
                resp = self.mem_resp_if.pop()

                pc_int_resp = resp.pc.int if isinstance(resp.pc, Bits) else int(resp.pc)
                data_bits = Bits(resp.packet)

                self._fill_from_response(pc_int_resp, data_bits)

                self._send_valid(True, data_bits[24], resp.warp_id)
                self.pending = False
                if self.ahead_latch.ready_for_push():
                    self.ahead_latch.push(resp)
                else:
                    _is_stalled = True

            # still pending — stalled waiting on memory
            else:
                print(f"[I$] waiting on memory")
                _is_stalled = True
                self._send_valid(False, False, 0)

                if self.req_latched:
                    if self.mem_req_if.ready_for_push():
                        print("[I$] Memrequest ACCEPTED by Memory")
                        self.mem_req_if.push(self.req)
                        self.req_latched = False

        else:
            # check to see if scheduler is even fetching
            if self.behind_latch.valid:
                _is_busy = True
                fetch = self.behind_latch.pop()
                pc_int = fetch.pc.int if isinstance(fetch.pc, Bits) else int(fetch.pc)

                line_lookup = self._lookup(pc_int)

                # in the cache — hit
                if line_lookup:
                    _is_hit = True
                    self._send_valid(True, line_lookup.data[24], fetch.warp_id)
                    fetch.packet = line_lookup.data

                    if self.ahead_latch.ready_for_push():
                        self.ahead_latch.push(fetch)
                    else:
                        _is_stalled = True

                # not in cache — miss
                else:
                    _is_miss = True
                    self._send_valid(False, False, 0)
                    self.pending = True

                    set_idx, tag, block = self._addr_decode(pc_int)
                    block_base = block * self.block_size
                    self.req = {
                        "addr": block_base,
                        "size": self.block_size,
                        "uuid": block,
                        "pc": pc_int,
                        "warp": fetch.warp_id,
                        "warpGroup": fetch.warp_group_id,
                        "inst": fetch
                    }

                    if self.mem_req_if.ready_for_push():
                        print("[I$] Memrequest ACCEPTED by Memory")
                        self.mem_req_if.push(self.req)
                        self.req_latched = False
                    else:
                        print("[I$] Memrequest STALLED due tobusy memory")
                        self.req_latched = True

            # scheduler not fetching and no pending request — idle
            else:
                self._send_valid(True, False, 0)

        self.perf_count.record_cycle(
            is_stalled=_is_stalled,
            is_busy=_is_busy,
            is_hit=_is_hit,
            is_miss=_is_miss,
        )

        self.cycle += 1
        return