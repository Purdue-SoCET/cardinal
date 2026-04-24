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
TEXEL_SIZE = 4       # 4 Bytes per Texel
LINE_SIZE = 128      # 128 Bytes per Cache Line
CACHE_SIZE = 16384   # 16 KB Total Cache Size
NUM_LINES = CACHE_SIZE // LINE_SIZE # 128 lines
ASSOC = 4
NUM_SETS = NUM_LINES // ASSOC

HIT_LATENCY = 1
MISS_PENALTY = 50

# Specific buffer sizes based on your team's design
N_D_CACHE = 16       # D-Cache MSHR size
N_T_HYBRID = 200     # T-Cache Frag FIFO (2N), Miss Req FIFO (N), ROB (N)

# ==========================================
# BIT MANIPULATION & ADDRESSING
# ==========================================
def interleave_bits(x, y):
    """Interleave 16-bit x and y into a 32-bit Morton code (Z-order)."""
    B = [0x55555555, 0x33333333, 0x0F0F0F0F, 0x00FF00FF]
    S = [1, 2, 4, 8]
    for i in range(4):
        x = (x | (x << S[3-i])) & B[3-i]
        y = (y | (y << S[3-i])) & B[3-i]
    return x | (y << 1)

def deinterleave_bits(z):
    """Convert a Morton code back into X, Y coordinates."""
    x = z & 0x55555555
    y = (z >> 1) & 0x55555555
    for _ in range(4):
        x = (x | (x >> 1)) & 0x33333333
        x = (x | (x >> 2)) & 0x0F0F0F0F
        x = (x | (x >> 4)) & 0x00FF00FF
        x = (x | (x >> 8)) & 0x0000FFFF
        
        y = (y | (y >> 1)) & 0x33333333
        y = (y | (y >> 2)) & 0x0F0F0F0F
        y = (y | (y >> 4)) & 0x00FF00FF
        y = (y | (y >> 8)) & 0x0000FFFF
    return x, y

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

def get_row_major_addr(u, v, mip=0):
    w = max(1, TEX_WIDTH >> mip)
    return get_mip_offset(mip) + (v * w + u) * TEXEL_SIZE

def get_morton_addr(u, v, mip=0):
    return get_mip_offset(mip) + interleave_bits(u, v) * TEXEL_SIZE

# ==========================================
# MEMORY BUS ARBITER
# ==========================================
class MemoryBus:
    """
    Simulates memory port contention. 
    If fills_per_cycle is 1, and 4 misses happen in the same cycle,
    they are scheduled across 4 consecutive cycles.
    """
    def __init__(self, fills_per_cycle):
        self.fills_per_cycle = fills_per_cycle
        self.available_slots = {} # cycle -> slots used
        
    def request_fill(self, current_cycle):
        c = current_cycle
        # Find the earliest cycle (>= current) that has available memory bus bandwidth
        while self.available_slots.get(c, 0) >= self.fills_per_cycle:
            c += 1
        self.available_slots[c] = self.available_slots.get(c, 0) + 1
        
        # Data arrives MISS_PENALTY cycles after it is successfully scheduled on the bus
        return c + MISS_PENALTY

# ==========================================
# SIMULATOR CLASSES
# ==========================================
class DCacheSimulator:
    def __init__(self, name, fills_per_cycle):
        self.name = name
        self.sets = [[] for _ in range(NUM_SETS)]
        self.seen_blocks = set()
        self.unique_texels = set()
        
        self.mshr = {} # block_addr -> ready_cycle
        self.bus = MemoryBus(fills_per_cycle)
        
        self.accesses = 0; self.hits = 0; self.misses = 0
        self.compulsory_misses = 0; self.line_fills = 0; self.cycles = 0

    def access_batch(self, texel_addrs):
        self.cycles += 1
        
        # Retire completed requests from MSHR
        completed = [a for a, r in self.mshr.items() if r <= self.cycles]
        for a in completed: del self.mshr[a]

        for addr in texel_addrs:
            self.accesses += 1
            self.unique_texels.add(addr)
            
            block = addr // LINE_SIZE
            set_idx = block % NUM_SETS
            tag = block // NUM_SETS

            # 1. Hit Path
            if tag in self.sets[set_idx]:
                self.hits += 1
                self.sets[set_idx].remove(tag)
                self.sets[set_idx].insert(0, tag)
                
            # 2. Miss Path (Coalesced in MSHR)
            elif block in self.mshr:
                self.misses += 1
                
            # 3. New Miss Path
            else:
                # Stall pipeline if MSHR is full (backpressure)
                while len(self.mshr) >= N_D_CACHE:
                    self.cycles += 1
                    comp = [a for a, r in self.mshr.items() if r <= self.cycles]
                    for a in comp: del self.mshr[a]
                
                self.misses += 1
                if block not in self.seen_blocks:
                    self.compulsory_misses += 1
                    self.seen_blocks.add(block)
                
                self.line_fills += 1
                ready_cycle = self.bus.request_fill(self.cycles)
                self.mshr[block] = ready_cycle
                
                # Evict LRU
                self.sets[set_idx].insert(0, tag)
                if len(self.sets[set_idx]) > ASSOC: self.sets[set_idx].pop()

    def flush(self):
        """Simulate remaining cycles to clear all pending memory operations."""
        if self.mshr: self.cycles = max(self.mshr.values())

    def get_stats(self):
        fetched = self.line_fills * LINE_SIZE
        useful = len(self.unique_texels) * TEXEL_SIZE
        return {
            "accesses": self.accesses, "hits": self.hits, "misses": self.misses, 
            "hit_rate": self.hits / max(1, self.accesses),
            "miss_rate": self.misses / max(1, self.accesses),
            "conflict_misses": self.misses - self.compulsory_misses,
            "bytes_fetched": fetched, "useful_bytes": useful, 
            "bw_efficiency": (useful/max(1,fetched))*100, 
            "total_cycles": self.cycles,
            "amat": HIT_LATENCY + ((self.misses/max(1, self.accesses))*MISS_PENALTY)
        }

class TCacheHybridSimulator:
    def __init__(self, name, fills_per_cycle):
        self.name = name
        self.sets = [[] for _ in range(NUM_SETS)]
        self.seen_blocks = set(); self.unique_texels = set()
        
        self.frag_fifo = []
        self.miss_req_fifo = [] 
        self.rob = []
        self.bus = MemoryBus(fills_per_cycle)
        self.last_pushed_addr = None 
        
        self.frag_size = 2 * N_T_HYBRID
        self.fifo_size = N_T_HYBRID
        
        self.accesses = 0; self.hits = 0; self.misses = 0
        self.compulsory_misses = 0; self.line_fills = 0; self.cycles = 0

    def tick(self):
        self.cycles += 1
        
        # Retire from FIFOs
        while self.miss_req_fifo and self.miss_req_fifo[0][1] <= self.cycles: self.miss_req_fifo.pop(0)
        while self.rob and self.rob[0] <= self.cycles: self.rob.pop(0)

        processed = 0
        current_cycle_misses = {} 

        # Controller pulls up to 4 from Frag FIFO
        while processed < 4 and self.frag_fifo:
            if len(self.rob) >= self.fifo_size: break
                
            addr = self.frag_fifo[0]; block = addr // LINE_SIZE
            set_idx = block % NUM_SETS; tag = block // NUM_SETS

            if tag in self.sets[set_idx]:
                self.hits += 1
                self.sets[set_idx].remove(tag); self.sets[set_idx].insert(0, tag)
                self.rob.append(self.cycles + HIT_LATENCY)
            else:
                self.misses += 1
                # Intra-cycle Hybrid Coalescing
                if block in current_cycle_misses:
                    self.rob.append(current_cycle_misses[block])
                # Inter-cycle Tail Check Coalescing
                elif block == self.last_pushed_addr and self.miss_req_fifo:
                    self.rob.append(self.miss_req_fifo[-1][1])
                else:
                    if len(self.miss_req_fifo) >= self.fifo_size: break
                    
                    if block not in self.seen_blocks:
                        self.compulsory_misses += 1
                        self.seen_blocks.add(block)
                    
                    self.line_fills += 1
                    ready_cycle = self.bus.request_fill(self.cycles)
                    
                    self.miss_req_fifo.append((block, ready_cycle))
                    self.last_pushed_addr = block
                    current_cycle_misses[block] = ready_cycle
                    self.rob.append(ready_cycle)
                    
                    self.sets[set_idx].insert(0, tag)
                    if len(self.sets[set_idx]) > ASSOC: self.sets[set_idx].pop()
            
            self.frag_fifo.pop(0)
            processed += 1

    def access_batch(self, texel_addrs):
        for addr in texel_addrs:
            self.accesses += 1; self.unique_texels.add(addr)
            
        # Backpressure if Fragment FIFO is full
        while len(self.frag_fifo) + len(texel_addrs) > self.frag_size:
            self.tick()
        self.frag_fifo.extend(texel_addrs)

    def flush(self):
        while self.frag_fifo or self.rob: self.tick()

    def get_stats(self):
        fetched = self.line_fills * LINE_SIZE; useful = len(self.unique_texels) * TEXEL_SIZE
        return {
            "accesses": self.accesses, "hits": self.hits, "misses": self.misses, 
            "hit_rate": self.hits / max(1, self.accesses),
            "miss_rate": self.misses / max(1, self.accesses),
            "conflict_misses": self.misses - self.compulsory_misses,
            "bytes_fetched": fetched, "useful_bytes": useful, 
            "bw_efficiency": (useful/max(1,fetched))*100, 
            "total_cycles": self.cycles,
            "amat": HIT_LATENCY + ((self.misses/max(1, self.accesses))*MISS_PENALTY)
        }

# ==========================================
# WORKLOAD LOGIC
# ==========================================
def get_texels_for_pixel(s, t, filter_type):
    s, t = max(0.0, min(1.0, s)), max(0.0, min(1.0, t))
    u_f, v_f = s * (TEX_WIDTH - 1), t * (TEX_HEIGHT - 1)
    
    if filter_type == "nearest": return [(int(round(u_f)), int(round(v_f)), 0)]
    
    # Bilinear
    u0, v0 = int(u_f), int(v_f)
    u1, v1 = min(u0 + 1, TEX_WIDTH - 1), min(v0 + 1, TEX_HEIGHT - 1)
    return [(u0, v0, 0), (u1, v0, 0), (u0, v1, 0), (u1, v1, 0)]

def run_experiment(uv_pairs, filter_type, fills_per_cycle):
    d_cache = DCacheSimulator("D-Cache", fills_per_cycle)
    t_cache = TCacheHybridSimulator("T-Cache Hybrid", fills_per_cycle)
    
    # Extract ALL texels flatly to enforce the 4-texel-per-cycle pipeline constraint
    all_texels = []
    for s, t in uv_pairs:
        all_texels.extend(get_texels_for_pixel(s, t, filter_type))
        
    # Send EXACTLY 4 texels per cycle
    for i in range(0, len(all_texels), 4):
        batch_texels = all_texels[i:i+4]
        
        d_addrs = [get_row_major_addr(u, v, mip) for u, v, mip in batch_texels]
        t_addrs = [get_morton_addr(u, v, mip) for u, v, mip in batch_texels]
            
        d_cache.access_batch(d_addrs)
        t_cache.access_batch(t_addrs)
        
    d_cache.flush()
    t_cache.flush()
    return d_cache.get_stats(), t_cache.get_stats()

# ==========================================
# GRAPHING UTILITIES
# ==========================================
def generate_graphs(results, filter_type):
    """Generates grouped bar charts displaying both memory constraints side by side."""
    workloads = list(results[1].keys())
    metrics = {
        'Total Execution Cycles': 'total_cycles',
        'Bandwidth Efficiency (%)': 'bw_efficiency',
        'Bytes Fetched': 'bytes_fetched'
    }
    
    import numpy as np
    x = np.arange(len(workloads))
    width = 0.2
    
    for title, key in metrics.items():
        # Extrapolate data: [workload][constraint] -> D or T stat
        d_1 = [results[1][wl][0][key] for wl in workloads]
        t_1 = [results[1][wl][1][key] for wl in workloads]
        d_2 = [results[2][wl][0][key] for wl in workloads]
        t_2 = [results[2][wl][1][key] for wl in workloads]
        
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar(x - 1.5*width, d_1, width, label='D-Cache (1 fill/cyc)', color='lightcoral')
        ax.bar(x - 0.5*width, t_1, width, label='T-Cache (1 fill/cyc)', color='darkred')
        ax.bar(x + 0.5*width, d_2, width, label='D-Cache (2 fills/cyc)', color='lightblue')
        ax.bar(x + 1.5*width, t_2, width, label='T-Cache (2 fills/cyc)', color='steelblue')
        
        ax.set_ylabel(title)
        ax.set_title(f'{title} Comparison ({filter_type.capitalize()}) - Memory Port Constraints')
        ax.set_xticks(x)
        ax.set_xticklabels([w.capitalize() for w in workloads])
        ax.legend()
        
        plt.tight_layout()
        filename = f"{key}_bus_comparison.png"
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
        
    trace_path = sys.argv[1]
    filter_mode = sys.argv[2].lower()
    
    # Generate Synthetic Workloads
    print("Generating Synthetic Workloads...")
    workloads = {"constant": [], "morton_smooth": [], "random": [], "trace": []}
    
    workloads["constant"] = [(0.5, 0.5) for _ in range(5000)]
    workloads["random"] = [(random.random(), random.random()) for _ in range(5000)]
    
    # Morton Smooth Trace: 10,000 steps following Z-order curve
    for i in range(10000):
        u, v = deinterleave_bits(i)
        workloads["morton_smooth"].append((u / (TEX_WIDTH - 1), v / (TEX_HEIGHT - 1)))
        
    # File Trace
    if os.path.exists(trace_path):
        with open(trace_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                match = re.search(r'S:([+-]?\d+\.\d+)\s+T:([+-]?\d+\.\d+)', line)
                if match:
                    workloads["trace"].append((float(match.group(1)), float(match.group(2))))
    else:
        print(f"Warning: Trace file '{trace_path}' not found. Trace graph will be empty.")
        del workloads["trace"]

    # all_results[constraint][workload] = (d_stats, t_stats)
    all_results = {1: {}, 2: {}}

    for bus_constraint in [1, 2]:
        print(f"\n{'='*25} MEMORY CONSTRAINT: {bus_constraint} FILL(S) / CYCLE {'='*25}")
        
        for name, uv in workloads.items():
            print(f"\n--- Running Workload: {name} ---")
            d_stats, t_stats = run_experiment(uv, filter_mode, bus_constraint)
            all_results[bus_constraint][name] = (d_stats, t_stats)
            
            print(f"{'Metric':<20} | {'D-Cache':<15} | {'T-Cache Hybrid':<15}")
            print("-" * 55)
            keys = ["accesses", "misses", "bytes_fetched", "bw_efficiency", "total_cycles"]
            for k in keys:
                v_d, v_t = d_stats[k], t_stats[k]
                if 'efficiency' in k:
                    print(f"{k:<20} | {v_d:<15.4f} | {v_t:<15.4f}")
                else:
                    print(f"{k:<20} | {v_d:<15} | {v_t:<15}")
                    
            cyc_red = (1 - (t_stats['total_cycles'] / max(1, d_stats['total_cycles']))) * 100
            print(f"> Cycle Reduction: {cyc_red:.2f}%")

    print("\nGenerating MATPLOTLIB Graphs...")
    generate_graphs(all_results, filter_mode)