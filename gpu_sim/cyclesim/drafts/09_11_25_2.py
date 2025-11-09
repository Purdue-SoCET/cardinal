# Example backend (instant dictionary backend)
from typing import Dict
from icache_base import L1ICache, FetchRequest

class DictMemoryBackend:
    def __init__(self):
        self.mem: Dict[int, bytearray] = {}

    def read_block(self, block_addr, block_size):
        return self.mem.get(block_addr, bytearray([0xCC] * block_size))

    def write_block(self, block_addr, data):
        self.mem[block_addr] = bytearray(data)


# Example config
cache_config = {
    "cache_size": 32768,    # 32 KB
    "block_size": 64,
    "associativity": 4,
    "miss_latency": 5
}

policies = {
    "replacement": "LRU",        # or "FIFO", "Random"
    "miss_handling": "non-blocking", # or "non-blocking"
    "prefetch": "next-line"      # or "none"
}

backend = DictMemoryBackend()
icache = L1ICache(cache_config, backend, policies)

# Simulate a few fetch cycles
for pc in [0x1000, 0x1040, 0x1080, 0x1000]:
    icache.accept_request(FetchRequest(uuid=pc, pc=pc, warp_id=0))

for cycle in range(40):
    icache.cycle()
    while icache.resp_queue:
        r = icache.resp_queue.popleft()
        print(f"Cycle {cycle:02d}: PC=0x{r.pc:X}, Hit={r.hit}")
