import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Any

# Base functional unit (for consistency)
class FunctionalUnit:
    def __init__(self, name: str):
        self.name = name

    def cycle(self):
        pass


@dataclass
class FetchRequest:
    uuid: int
    pc: int
    warp_id: int


@dataclass
class FetchResponse:
    uuid: int
    pc: int
    data: bytearray
    hit: bool


class L1ICache(FunctionalUnit):
    def __init__(self, cache_config: Dict[str, Any], backend, policies: Dict[str, str]):
        super().__init__("L1_ICache")

        # --- Configuration ---
        self.cache_size = cache_config["cache_size"]
        self.block_size = cache_config["block_size"]
        self.associativity = cache_config["associativity"]
        self.num_banks = cache_config.get("num_banks", 1)
        self.miss_latency = cache_config.get("miss_latency", 50)
        self.backend = backend  # MemoryBackend interface

        # --- Policies ---
        self.replacement_policy = policies.get("replacement", "LRU")
        self.miss_policy = policies.get("miss_handling", "blocking")  # blocking or non-blocking
        self.prefetch_policy = policies.get("prefetch", "none")  # none, next-line, stride

        # --- Derived parameters ---
        total_sets = self.cache_size // (self.block_size * self.associativity)
        self.set_bits = int(math.log2(total_sets))
        self.offset_bits = int(math.log2(self.block_size))
        self.num_sets = total_sets

        # --- Structures ---
        self.cache = [
            [{"tag": None, "valid": False, "lru": 0, "data": bytearray(self.block_size)}
             for _ in range(self.associativity)]
            for _ in range(self.num_sets)
        ]
        self.lru_counter = 0

        # --- Queues ---
        self.req_queue = deque()
        self.resp_queue = deque()
        self.active_miss: Optional[Dict] = None  # holds {tag, set_idx, countdown, uuid, pc}

    # --- Helper: Address Parsing ---
    def _parse_address(self, addr: int) -> Tuple[int, int, int]:
        block_addr = addr >> self.offset_bits
        set_idx = block_addr & ((1 << self.set_bits) - 1)
        tag = block_addr >> self.set_bits
        return tag, set_idx, block_addr

    # --- Helper: Replacement Policy ---
    def _choose_victim_way(self, set_idx: int) -> int:
        ways = self.cache[set_idx]
        if self.replacement_policy == "Random":
            return random.randint(0, self.associativity - 1)
        elif self.replacement_policy == "FIFO":
            return min(range(self.associativity), key=lambda i: ways[i]["lru"])
        else:  # Default = LRU
            return min(range(self.associativity), key=lambda i: ways[i]["lru"])

    # --- Helper: Update Replacement State ---
    def _update_replacement_state(self, set_idx: int, way: int):
        self.lru_counter += 1
        self.cache[set_idx][way]["lru"] = self.lru_counter

    # --- API: Accept Fetch Request ---
    def accept_request(self, req: FetchRequest):
        self.req_queue.append(req)

    # --- Cycle-level operation ---
    def cycle(self):
        # --- Step 1: Handle Active Miss ---
        if self.active_miss:
            self.active_miss["countdown"] -= 1
            if self.active_miss["countdown"] == 0:
                tag = self.active_miss["tag"]
                set_idx = self.active_miss["set_idx"]
                uuid = self.active_miss["uuid"]
                pc = self.active_miss["pc"]

                # Fill from backend
                block_data = self.backend.read_block(self.active_miss["block_addr"], self.block_size)
                victim = self._choose_victim_way(set_idx)
                self.cache[set_idx][victim].update({
                    "tag": tag,
                    "valid": True,
                    "data": block_data
                })
                self._update_replacement_state(set_idx, victim)
                self.active_miss = None

                # Return response
                self.resp_queue.append(FetchResponse(uuid=uuid, pc=pc, data=block_data, hit=False))

        # --- Step 2: Handle New Requests ---
        if self.req_queue:
            req = self.req_queue.popleft()
            tag, set_idx, block_addr = self._parse_address(req.pc)
            hit_way = None

            # Check tag match
            for w in range(self.associativity):
                line = self.cache[set_idx][w]
                if line["valid"] and line["tag"] == tag:
                    hit_way = w
                    break

            if hit_way is not None:
                # Cache hit
                self._update_replacement_state(set_idx, hit_way)
                block_data = self.cache[set_idx][hit_way]["data"]
                self.resp_queue.append(FetchResponse(req.uuid, req.pc, block_data, hit=True))
            else:
                # Cache miss
                if self.miss_policy == "non-blocking" and self.active_miss:
                    # Stall until current miss completes
                    self.req_queue.appendleft(req)
                    return

                # Launch miss
                self.active_miss = {
                    "tag": tag,
                    "set_idx": set_idx,
                    "block_addr": block_addr,
                    "uuid": req.uuid,
                    "pc": req.pc,
                    "countdown": self.miss_latency
                }

                # (Optional) Prefetch next line
                if self.prefetch_policy == "next-line":
                    next_block = block_addr + 1
                    self.backend.read_block(next_block, self.block_size)

