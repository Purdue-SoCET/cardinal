'''
D-cache with MSHR (Non-Blocking), no Frag FIFO, tightly coupled tag/data, blocking on misses.
T-cache with Miss Request FIFO and ROB, using tail register and duplicate requests in same cycle and  decoupled tag/data, allows coalescing of misses within ROB depth N.
Both caches are 16KB, 128B line size, 4-way set associative.'''
import sys
import re
import os
import random
import matplotlib.pyplot as plt

# ==========================================
# CONFIGURATION & CONSTANTS
# ==========================================
TEX_WIDTH = 1024
TEX_HEIGHT = 1024
TEXEL_SIZE = 4       # Bytes
LINE_SIZE = 128      # Bytes
CACHE_SIZE = 16384   # 16 KB
NUM_LINES = CACHE_SIZE // LINE_SIZE # 128 lines
ASSOC = 4
NUM_SETS = NUM_LINES // ASSOC

HIT_LATENCY = 1
MISS_PENALTY = 50
N_SIZE = 16          # Variable N for FIFO sizing

# ==========================================
# ADDRESS CALCULATION UTILITIES
# ==========================================
# ==========================================
# TODO || VERIFIED
# ==========================================
def interleave_bits(x, y):
    """Interleave 16-bit x and y into a 32-bit Morton code."""
    B = [0x55555555, 0x33333333, 0x0F0F0F0F, 0x00FF00FF]
    S = [1, 2, 4, 8]

    x = (x | (x << S[3])) & B[3]
    x = (x | (x << S[2])) & B[2]
    x = (x | (x << S[1])) & B[1]
    x = (x | (x << S[0])) & B[0]

    y = (y | (y << S[3])) & B[3]
    y = (y | (y << S[2])) & B[2]
    y = (y | (y << S[1])) & B[1]
    y = (y | (y << S[0])) & B[0]

    return x | (y << 1)

def get_mip_offset(level):
    offset = 0
    w, h = TEX_WIDTH, TEX_HEIGHT
    for _ in range(level):
        offset += w * h * TEXEL_SIZE
        w //= 2
        h //= 2
        if w == 0: w = 1
        if h == 0: h = 1
    return offset

def get_row_major_addr(u, v, mip_level=0):
    w = max(1, TEX_WIDTH >> mip_level)
    base = get_mip_offset(mip_level)
    return base + (v * w + u) * TEXEL_SIZE

def get_morton_addr(u, v, mip_level=0):
    base = get_mip_offset(mip_level)
    return base + interleave_bits(u, v) * TEXEL_SIZE

# ==========================================
# MICROARCHITECTURAL CACHE MODELS
# ==========================================
# ==========================================
# TODO || VERIFY
# ==========================================
class DCacheSimulator:
    """
    D-Cache with an MSHR (Non-Blocking).
    Lacks Fragment FIFO and ROB (Tag/Data arrays are tightly coupled).
    """
    def __init__(self, name):
        self.name = name
        self.sets = [[] for _ in range(NUM_SETS)]
        self.seen_blocks = set()
        self.unique_texels = set()
        
        # MSHR for miss-under-miss behavior (Block Addr -> Ready Cycle)
        self.mshr = {} 
        self.mshr_size = N_SIZE
        
        self.accesses = 0
        self.hits = 0
        self.misses = 0
        self.compulsory_misses = 0
        self.line_fills = 0
        self.cycles = 0

    def access_batch(self, texel_addrs):
        self.cycles += 1
        
        # Process memory returns
        completed = [addr for addr, ready in self.mshr.items() if ready <= self.cycles]
        for addr in completed:
            del self.mshr[addr]

        for addr in texel_addrs:
            self.accesses += 1
            self.unique_texels.add(addr)
            
            block_addr = addr // LINE_SIZE
            set_idx = block_addr % NUM_SETS
            tag = block_addr // NUM_SETS
            
            # 1. Hit Path
            if tag in self.sets[set_idx]:
                self.hits += 1
                self.sets[set_idx].remove(tag)
                self.sets[set_idx].insert(0, tag)
                
            # 2. Miss Path (Coalesced in MSHR)
            elif block_addr in self.mshr:
                self.misses += 1
                
            # 3. Miss Path (True Structural Miss)
            else:
                # Stall pipeline if MSHR is full (head-of-line blocking resumes)
                while len(self.mshr) >= self.mshr_size:
                    self.cycles += 1
                    completed = [a for a, r in self.mshr.items() if r <= self.cycles]
                    for a in completed: del self.mshr[a]
                
                self.misses += 1
                if block_addr not in self.seen_blocks:
                    self.compulsory_misses += 1
                    self.seen_blocks.add(block_addr)
                
                self.line_fills += 1
                self.mshr[block_addr] = self.cycles + MISS_PENALTY
                
                self.sets[set_idx].insert(0, tag)
                if len(self.sets[set_idx]) > ASSOC:
                    self.sets[set_idx].pop()

    def flush(self):
        if self.mshr:
            self.cycles = max(self.mshr.values())
            self.mshr.clear()

    def get_stats(self):
        bytes_fetched = self.line_fills * LINE_SIZE
        useful_bytes = len(self.unique_texels) * TEXEL_SIZE
        bw_eff = (useful_bytes / max(1, bytes_fetched)) * 100
        redundant_texels = (bytes_fetched - useful_bytes) / TEXEL_SIZE
        
        return {
            "accesses": self.accesses,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / max(1, self.accesses),
            "miss_rate": self.misses / max(1, self.accesses),
            "compulsory_misses": self.compulsory_misses,
            "conflict_misses": self.misses - self.compulsory_misses,
            "line_fills": self.line_fills,
            "bytes_fetched": bytes_fetched,
            "useful_bytes": useful_bytes,
            "bw_efficiency": bw_eff,
            "redundant_texels": redundant_texels,
            "amat": HIT_LATENCY + ((self.misses / max(1, self.accesses)) * MISS_PENALTY),
            "total_cycles": self.cycles
        }

# ==========================================
# TODO || VERIFY
# ==========================================
class TCacheSimulator:
    """
    T-Cache using a Hybrid Coalescing approach:
    1. Intra-cycle batch coalescing.
    2. Inter-cycle Tail-check against the Miss Request FIFO.
    """
    def __init__(self, name):
        self.name = name
        self.sets = [[] for _ in range(NUM_SETS)]
        self.seen_blocks = set()
        self.unique_texels = set()
        
        self.frag_fifo = []
        self.miss_req_fifo = []      # Stores tuples of (block_addr, ready_cycle)
        self.rob = []
        self.last_pushed_addr = None # Tail register for inter-cycle coalescing
        
        self.frag_size = 2 * 50
        self.fifo_size = 50
        
        self.accesses = 0
        self.hits = 0
        self.misses = 0
        self.compulsory_misses = 0
        self.line_fills = 0
        self.cycles = 0

    def tick(self):
        self.cycles += 1
        
        # Retire completed requests
        while self.miss_req_fifo and self.miss_req_fifo[0][1] <= self.cycles:
            self.miss_req_fifo.pop(0)
        while self.rob and self.rob[0] <= self.cycles:
            self.rob.pop(0)

        processed = 0
        current_cycle_misses = {} # For intra-cycle coalescing

        while processed < 4 and self.frag_fifo:
            if len(self.rob) >= self.fifo_size: 
                break # ROB backpressure
                
            addr = self.frag_fifo[0]
            block_addr = addr // LINE_SIZE
            set_idx = block_addr % NUM_SETS
            tag = block_addr // NUM_SETS

            # 1. Hit Path
            if tag in self.sets[set_idx]:
                self.hits += 1
                self.sets[set_idx].remove(tag)
                self.sets[set_idx].insert(0, tag)
                self.rob.append(self.cycles + HIT_LATENCY)
                self.frag_fifo.pop(0)
                processed += 1
                
            # 2. Miss Path
            else:
                self.misses += 1
                
                # Coalescing A: Intra-cycle (did we already miss on this line THIS cycle?)
                if block_addr in current_cycle_misses:
                    self.rob.append(current_cycle_misses[block_addr])
                    
                # Coalescing B: Inter-cycle (Tail Check)
                elif block_addr == self.last_pushed_addr and self.miss_req_fifo:
                    self.rob.append(self.miss_req_fifo[-1][1])
                    
                # True Miss (Requires Memory Fetch)
                else:
                    if len(self.miss_req_fifo) >= self.fifo_size: 
                        break # Miss FIFO full backpressure
                    
                    if block_addr not in self.seen_blocks:
                        self.compulsory_misses += 1
                        self.seen_blocks.add(block_addr)
                    
                    self.line_fills += 1
                    ready_cyc = self.cycles + MISS_PENALTY
                    
                    self.miss_req_fifo.append((block_addr, ready_cyc))
                    self.last_pushed_addr = block_addr
                    current_cycle_misses[block_addr] = ready_cyc
                    self.rob.append(ready_cyc)
                    
                    self.sets[set_idx].insert(0, tag)
                    if len(self.sets[set_idx]) > ASSOC: 
                        self.sets[set_idx].pop()
                
                self.frag_fifo.pop(0)
                processed += 1

    def access_batch(self, texel_addrs):
        for addr in texel_addrs:
            self.accesses += 1
            self.unique_texels.add(addr)
            
        while len(self.frag_fifo) + len(texel_addrs) > self.frag_size:
            self.tick()
        self.frag_fifo.extend(texel_addrs)

    def flush(self):
        while self.frag_fifo or self.rob: 
            self.tick()

    def get_stats(self):
        bytes_fetched = self.line_fills * LINE_SIZE
        useful_bytes = len(self.unique_texels) * TEXEL_SIZE
        bw_eff = (useful_bytes / max(1, bytes_fetched)) * 100
        redundant_texels = (bytes_fetched - useful_bytes) / TEXEL_SIZE
        return {
            "accesses": self.accesses, "hits": self.hits, "misses": self.misses,
            "hit_rate": self.hits / max(1, self.accesses),
            "miss_rate": self.misses / max(1, self.accesses),
            "compulsory_misses": self.compulsory_misses,
            "conflict_misses": self.misses - self.compulsory_misses,
            "line_fills": self.line_fills, "bytes_fetched": bytes_fetched,
            "useful_bytes": useful_bytes, "bw_efficiency": bw_eff,
            "redundant_texels": redundant_texels,
            "amat": HIT_LATENCY + ((self.misses / max(1, self.accesses)) * MISS_PENALTY),
            "total_cycles": self.cycles
        }


# ==========================================
# WORKLOAD GENERATION & FILTERING
# ==========================================
# ==========================================
# TODO || VERIFIED : UV parsed correctly and texel requests generated correctly according to filter type.
# ==========================================
def get_texels_for_pixel(s, t, filter_type):
    """Returns a list of (u, v, mip) tuples for a given ST coordinate."""
    s = max(0.0, min(1.0, s))
    t = max(0.0, min(1.0, t))
    u_float = s * (TEX_WIDTH - 1)
    v_float = t * (TEX_HEIGHT - 1)
    
    texels = []
    if filter_type == "nearest":
        texels.append((int(round(u_float)), int(round(v_float)), 0))
        
    elif filter_type == "bilinear":
        u0, v0 = int(u_float), int(v_float)
        u1, v1 = min(u0 + 1, TEX_WIDTH - 1), min(v0 + 1, TEX_HEIGHT - 1)
        texels.extend([(u0, v0, 0), (u1, v0, 0), (u0, v1, 0), (u1, v1, 0)])
        
    elif filter_type == "trilinear":
        u0, v0 = int(u_float), int(v_float)
        u1, v1 = min(u0 + 1, TEX_WIDTH - 1), min(v0 + 1, TEX_HEIGHT - 1)
        texels.extend([(u0, v0, 0), (u1, v0, 0), (u0, v1, 0), (u1, v1, 0)])
        
        u_float1 = s * ((TEX_WIDTH >> 1) - 1)
        v_float1 = t * ((TEX_HEIGHT >> 1) - 1)
        u0_1, v0_1 = int(u_float1), int(v_float1)
        u1_1, v1_1 = min(u0_1 + 1, (TEX_WIDTH >> 1) - 1), min(v0_1 + 1, (TEX_HEIGHT >> 1) - 1)
        texels.extend([(u0_1, v0_1, 1), (u1_1, v0_1, 1), (u0_1, v1_1, 1), (u1_1, v1_1, 1)])
        
    return texels

# ==========================================
# TODO || VERIFIED : All texel requests are generated and fed into the simulators correctly. Stats are collected and printed.
# ==========================================
def parse_and_run(filepath, filter_type, workload_name):
    print(f"\n--- Running Workload: {workload_name} ({filter_type}) ---")
    
    d_cache = DCacheSimulator("D-Cache (Row-Major)")
    t_cache = TCacheSimulator("T-Cache (Morton)")
    
    uv_pairs = []
    
    # Gracefully ignore binary encoding errors (0x89 PNG headers, etc)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                match = re.search(r'S:([+-]?\d+\.\d+)\s+T:([+-]?\d+\.\d+)', line)
                if match:
                    uv_pairs.append((float(match.group(1)), float(match.group(2))))
    else:
        print(f"File {filepath} not found. Generating synthetic {workload_name} trace...")
        if workload_name == "constant":
            uv_pairs = [(0.5, 0.5) for _ in range(5000)]
        elif workload_name == "smooth":
            uv_pairs = [((i*0.0001)%1.0, (i*0.0001)%1.0) for i in range(5000)]
        elif workload_name == "random":
            uv_pairs = [(random.random(), random.random()) for _ in range(5000)]
        else:
            uv_pairs = [((i*0.001)%1.0, (i*0.002)%1.0) for i in range(5000)]

    # Generate all texel requests
    texel_requests = []
    for s, t in uv_pairs:
        texel_requests.extend(get_texels_for_pixel(s, t, filter_type))

    # TMU sends 4 texel requests per cycle
    for i in range(0, len(texel_requests), 4):
        batch = texel_requests[i:i+4]
        
        d_addrs = [get_row_major_addr(u, v, mip) for u, v, mip in batch]
        t_addrs = [get_morton_addr(u, v, mip) for u, v, mip in batch]
        
        d_cache.access_batch(d_addrs)
        t_cache.access_batch(t_addrs)
        
    d_cache.flush()
    t_cache.flush()

    stats_d = d_cache.get_stats()
    stats_t = t_cache.get_stats()
    
    print_stats(stats_d, stats_t)
    return stats_d, stats_t

def print_stats(d_stats, t_stats):
    print("\nRESULTS SUMMARY:")
    print(f"{'Metric':<20} | {'D-Cache (Row)':<15} | {'T-Cache (Morton)':<15}")
    print("-" * 56)
    
    keys = ["accesses", "hits", "misses", "hit_rate", "miss_rate", "conflict_misses", 
            "bytes_fetched", "useful_bytes", "bw_efficiency", "redundant_texels", 
            "amat", "total_cycles"]
            
    for k in keys:
        v_d, v_t = d_stats[k], t_stats[k]
        if 'rate' in k or 'amat' in k or 'efficiency' in k:
            print(f"{k:<20} | {v_d:<15.4f} | {v_t:<15.4f}")
        else:
            print(f"{k:<20} | {v_d:<15} | {v_t:<15}")

    bw_ratio = t_stats['bytes_fetched'] / max(1, d_stats['bytes_fetched'])
    conflict_d = max(1, d_stats['conflict_misses'])
    conflict_ratio = t_stats['conflict_misses'] / conflict_d
    cyc_red = (1 - (t_stats['total_cycles'] / max(1, d_stats['total_cycles']))) * 100
    
    print("\nCOMPARISON:")
    print(f"Bandwidth Reduction:   {(1 - bw_ratio) * 100:.2f}%")
    print(f"Conflict Miss Reduc:   {(1 - conflict_ratio) * 100:.2f}%")
    print(f"Cycle Reduction:       {cyc_red:.2f}% (Thanks to T-Cache Latency Hiding!)")

# ==========================================
# GRAPHING UTILITIES
# ==========================================
def generate_graphs(results, filter_type):
    workloads = list(results.keys())
    
    metrics = {
        'Bandwidth Efficiency (%)': 'bw_efficiency',
        'Conflict Misses': 'conflict_misses',
        'AMAT (Cycles)': 'amat',
        'Total Execution Cycles': 'total_cycles'
    }
    
    for title, key in metrics.items():
        d_vals = [results[wl][0][key] for wl in workloads]
        t_vals = [results[wl][1][key] for wl in workloads]
        
        x = range(len(workloads))
        width = 0.35
        
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.bar([i - width/2 for i in x], d_vals, width, label='D-Cache (Row)', color='lightcoral')
        ax.bar([i + width/2 for i in x], t_vals, width, label='T-Cache (Morton)', color='steelblue')
        
        ax.set_ylabel(title)
        ax.set_title(f'{title} Comparison ({filter_type.capitalize()})')
        ax.set_xticks(list(x))
        ax.set_xticklabels([w.capitalize() for w in workloads])
        ax.legend()
        
        plt.tight_layout()
        filename = f"{key}_comparison.png"
        plt.savefig(filename)
        print(f"Saved graph: {filename}")
        plt.close()

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python data_compare.py <input_file> <filter_type>")
        sys.exit(1)
        
    trace_file = sys.argv[1]
    filter_type = sys.argv[2].lower()
    
    workloads = ["constant", "smooth", "trace", "random"]
    all_results = {}
    
    for wl in workloads:
        path_to_use = trace_file if wl == "trace" else f"synthetic_{wl}.txt"
        stats_d, stats_t = parse_and_run(path_to_use, filter_type, wl)
        all_results[wl] = (stats_d, stats_t)

    print("\nGenerating MATPLOTLIB Graphs...")
    generate_graphs(all_results, filter_type)