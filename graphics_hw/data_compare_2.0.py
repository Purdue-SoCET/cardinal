'''
D-cache without MSHR or Frag FIFO, tightly coupled tag/data, blocking on misses.
T-cache with MSHR and Frag FIFO, decoupled tag/data, allows coalescing of misses within ROB depth N.
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
    """Calculates byte offset for contiguous mip levels."""
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
# CACHE MODEL
# ==========================================
class CacheSimulator:
    def __init__(self, name, layout="morton"):
        self.name = name
        self.layout = layout
        self.sets = [[] for _ in range(NUM_SETS)] # LRU lists (front is MRU, back is LRU)
        self.seen_blocks = set() # For compulsory miss tracking
        self.pending_requests = set() # Coalescing / MSHR (Miss Req FIFO bounds implicitly handled)
        
        # Stats
        self.accesses = 0
        self.hits = 0
        self.misses = 0
        self.compulsory_misses = 0
        self.line_fills = 0
        
    def access(self, u, v, mip_level=0):
        self.accesses += 1
        
        # Address mapping
        if self.layout == "morton":
            addr = get_morton_addr(u, v, mip_level)
        else:
            addr = get_row_major_addr(u, v, mip_level)
            
        block_addr = addr // LINE_SIZE
        set_idx = block_addr % NUM_SETS
        tag = block_addr // NUM_SETS
        
        cache_set = self.sets[set_idx]
        
        # Hit Path
        if tag in cache_set:
            self.hits += 1
            # Update LRU
            cache_set.remove(tag)
            cache_set.insert(0, tag)
            return

        # Miss Path
        self.misses += 1
        
        if block_addr not in self.seen_blocks:
            self.compulsory_misses += 1
            self.seen_blocks.add(block_addr)
            
        # Coalescing: Check if already in Miss Req FIFO
        if block_addr not in self.pending_requests:
            self.pending_requests.add(block_addr)
            self.line_fills += 1
            
        # Insert into cache (evict LRU if needed)
        cache_set.insert(0, tag)
        if len(cache_set) > ASSOC:
            cache_set.pop() # Remove LRU

    def flush_pending(self):
        """Simulates memory returning the coalesced requests."""
        self.pending_requests.clear()

    def get_stats(self):
        hit_rate = self.hits / max(1, self.accesses)
        miss_rate = self.misses / max(1, self.accesses)
        conflict_misses = self.misses - self.compulsory_misses
        bytes_from_mem = self.line_fills * LINE_SIZE
        amat = HIT_LATENCY + (miss_rate * MISS_PENALTY)
        total_cycles = (self.hits * HIT_LATENCY) + (self.misses * MISS_PENALTY)
        
        return {
            "accesses": self.accesses,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "miss_rate": miss_rate,
            "compulsory_misses": self.compulsory_misses,
            "conflict_misses": conflict_misses,
            "line_fills": self.line_fills,
            "bytes_from_mem": bytes_from_mem,
            "amat": amat,
            "total_cycles": total_cycles
        }

# ==========================================
# WORKLOAD GENERATION & FILTERING
# ==========================================
def apply_filtering(cache, s, t, filter_type):
    # Clamp to [0.0, 1.0]
    s = max(0.0, min(1.0, s))
    t = max(0.0, min(1.0, t))
    
    u_float = s * (TEX_WIDTH - 1)
    v_float = t * (TEX_HEIGHT - 1)
    
    if filter_type == "nearest":
        cache.access(int(round(u_float)), int(round(v_float)), 0)
    
    elif filter_type == "bilinear":
        u0, v0 = int(u_float), int(v_float)
        u1, v1 = min(u0 + 1, TEX_WIDTH - 1), min(v0 + 1, TEX_HEIGHT - 1)
        cache.access(u0, v0, 0)
        cache.access(u1, v0, 0)
        cache.access(u0, v1, 0)
        cache.access(u1, v1, 0)
        
    elif filter_type == "trilinear":
        # Bilinear on Mip 0
        u0, v0 = int(u_float), int(v_float)
        u1, v1 = min(u0 + 1, TEX_WIDTH - 1), min(v0 + 1, TEX_HEIGHT - 1)
        for u, v in [(u0, v0), (u1, v0), (u0, v1), (u1, v1)]:
            cache.access(u, v, 0)
            
        # Bilinear on Mip 1
        u_float1 = s * ((TEX_WIDTH >> 1) - 1)
        v_float1 = t * ((TEX_HEIGHT >> 1) - 1)
        u0_1, v0_1 = int(u_float1), int(v_float1)
        u1_1, v1_1 = min(u0_1 + 1, (TEX_WIDTH >> 1) - 1), min(v0_1 + 1, (TEX_HEIGHT >> 1) - 1)
        for u, v in [(u0_1, v0_1), (u1_1, v0_1), (u0_1, v1_1), (u1_1, v1_1)]:
            cache.access(u, v, 1)

def parse_and_run(filepath, filter_type, workload_name):
    print(f"\n--- Running Workload: {workload_name} ({filter_type}) ---")
    
    d_cache = CacheSimulator("D-Cache (Row-Major)", "row-major")
    t_cache = CacheSimulator("T-Cache (Morton)", "morton")
    
    uv_pairs = []
    
    # Parse File or generate synthetic if missing
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            for line in f:
                match = re.search(r'S:([+-]?\d+\.\d+)\s+T:([+-]?\d+\.\d+)', line)
                if match:
                    uv_pairs.append((float(match.group(1)), float(match.group(2))))
    else:
        print(f"File {filepath} not found. Generating synthetic {workload_name} trace...")
        if workload_name == "constant":
            uv_pairs = [(0.5, 0.5) for _ in range(10000)]
        elif workload_name == "smooth":
            uv_pairs = [((i*0.0001)%1.0, (i*0.0001)%1.0) for i in range(10000)]
        elif workload_name == "random":
            uv_pairs = [(random.random(), random.random()) for _ in range(10000)]
        else: # trace fallback
            uv_pairs = [((i*0.001)%1.0, (i*0.002)%1.0) for i in range(10000)]

    # Simulate
    cycle = 0
    for i in range(0, len(uv_pairs), 4): # 4 pixels processed per cycle roughly
        batch = uv_pairs[i:i+4]
        for s, t in batch:
            apply_filtering(d_cache, s, t, filter_type)
            apply_filtering(t_cache, s, t, filter_type)
        
        # Flush pending requests periodically to simulate memory returning data
        # Assuming ROB depth N = 16, memory latency 50. 
        if cycle % 50 == 0: 
            d_cache.flush_pending()
            t_cache.flush_pending()
        cycle += 1

    stats_d = d_cache.get_stats()
    stats_t = t_cache.get_stats()
    
    print_stats(stats_d, stats_t)
    return stats_d, stats_t

def print_stats(d_stats, t_stats):
    print("\nRESULTS SUMMARY:")
    print(f"{'Metric':<20} | {'D-Cache (Row)':<15} | {'T-Cache (Morton)':<15}")
    print("-" * 56)
    
    keys = ["accesses", "hits", "misses", "hit_rate", "miss_rate", "compulsory_misses", 
            "conflict_misses", "line_fills", "bytes_from_mem", "amat", "total_cycles"]
            
    for k in keys:
        v_d, v_t = d_stats[k], t_stats[k]
        if 'rate' in k or 'amat' in k:
            print(f"{k:<20} | {v_d:<15.4f} | {v_t:<15.4f}")
        else:
            print(f"{k:<20} | {v_d:<15} | {v_t:<15}")

    # Comparative Metrics
    bw_ratio = t_stats['bytes_from_mem'] / max(1, d_stats['bytes_from_mem'])
    bw_reduction = (1 - bw_ratio) * 100
    
    conflict_d = max(1, d_stats['conflict_misses'])
    conflict_ratio = t_stats['conflict_misses'] / conflict_d
    conflict_reduction = (1 - conflict_ratio) * 100
    
    amat_red = (1 - (t_stats['amat'] / d_stats['amat'])) * 100
    cyc_red = (1 - (t_stats['total_cycles'] / d_stats['total_cycles'])) * 100
    
    print("\nCOMPARISON:")
    print(f"Bandwidth Ratio:       {bw_ratio:.4f}")
    print(f"Bandwidth Reduction:   {bw_reduction:.2f}%")
    print(f"Conflict Miss Ratio:   {conflict_ratio:.4f}")
    print(f"Conflict Miss Reduc:   {conflict_reduction:.2f}%")
    print(f"AMAT Reduction:        {amat_red:.2f}%")
    print(f"Cycle Reduction:       {cyc_red:.2f}%")

# ==========================================
# GRAPHING UTILITIES
# ==========================================
def generate_graphs(results, filter_type):
    workloads = list(results.keys())
    
    metrics = {
        'Bandwidth (Bytes)': 'bytes_from_mem',
        'Conflict Misses': 'conflict_misses',
        'AMAT (Cycles)': 'amat',
        'Total Cycles': 'total_cycles'
    }
    
    for title, key in metrics.items():
        d_vals = [results[wl][0][key] for wl in workloads]
        t_vals = [results[wl][1][key] for wl in workloads]
        
        x = range(len(workloads))
        width = 0.35
        
        fig, ax = plt.subplots(figsize=(8, 5))
        rects1 = ax.bar([i - width/2 for i in x], d_vals, width, label='D-Cache (Row-Major)', color='lightcoral')
        rects2 = ax.bar([i + width/2 for i in x], t_vals, width, label='T-Cache (Morton)', color='steelblue')
        
        ax.set_ylabel(title)
        ax.set_title(f'{title} Comparison ({filter_type.capitalize()} Filter)')
        ax.set_xticks(list(x))
        ax.set_xticklabels([w.capitalize() for w in workloads])
        ax.legend()
        
        plt.tight_layout()
        filename = f"{title.split()[0].lower()}_comparison.png"
        plt.savefig(filename)
        print(f"Saved graph: {filename}")
        plt.close()

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python data_compare.py <input_file> <filter_type>")
        print("Example: python data_compare.py pixeldebug_UV.txt bilinear")
        sys.exit(1)
        
    trace_file = sys.argv[1]
    filter_type = sys.argv[2].lower()
    
    if filter_type not in ["nearest", "bilinear", "trilinear"]:
        print("Invalid filter. Use nearest, bilinear, or trilinear.")
        sys.exit(1)

    # Run all 4 workload types
    workloads = ["constant", "smooth", "trace", "random"]
    all_results = {}
    
    for wl in workloads:
        # If workload is 'trace', use the user-provided file. Otherwise, generate synthetics.
        path_to_use = trace_file if wl == "trace" else f"synthetic_{wl}.txt"
        stats_d, stats_t = parse_and_run(path_to_use, filter_type, wl)
        all_results[wl] = (stats_d, stats_t)

    # Generate the 4 comparative graphs
    print("\nGenerating MATPLOTLIB Graphs...")
    generate_graphs(all_results, filter_type)