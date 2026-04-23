"""
D-Cache vs T-Cache Texture Access Simulation
=============================================
Realistic workload: rasterising textured quads/triangles where UV coordinates
vary smoothly across the primitive (as in real GPU rasterisation).

Three workloads:
  1. Full-screen quad   — texture mapped 1:1 (good locality)
  2. Perspective quad   — non-uniform UV stretch (mixed locality)
  3. Minified quad      — many texels skipped per fragment (poor locality)

Morton ordering assumed for texture storage in both caches.

Fixes vs previous version:
  - useful_bytes tracks UNIQUE texels touched per cache line (not hit count)
    so bandwidth efficiency can never exceed 100%
  - D-Cache throughput = 1 cache-line per cycle (not 1 texel per cycle)
    giving a fairer comparison before T-Cache's 16-wide banks still win
"""

import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict
from typing import List, Tuple, Dict, Set

# ─────────────────────────────────────────────────────────────
# Morton helpers
# ─────────────────────────────────────────────────────────────

def spread_bits(x: int) -> int:
    x &= 0xFFFF
    x = (x | (x << 8))  & 0x00FF00FF
    x = (x | (x << 4))  & 0x0F0F0F0F
    x = (x | (x << 2))  & 0x33333333
    x = (x | (x << 1))  & 0x55555555
    return x

def morton_encode(x: int, y: int) -> int:
    return spread_bits(x) | (spread_bits(y) << 1)

# ─────────────────────────────────────────────────────────────
# Scene / cache constants
# ─────────────────────────────────────────────────────────────

TEXEL_BYTES            = 4
TEX_W, TEX_H           = 128, 128

DCACHE_LINE_BYTES      = 16
DCACHE_LINE_TEXELS     = DCACHE_LINE_BYTES // TEXEL_BYTES   # 32
DCACHE_NUM_LINES       = 512

TCACHE_TILE_W          = 4
TCACHE_TILE_H          = 4
TCACHE_TILE_TEXELS     = TCACHE_TILE_W * TCACHE_TILE_H      # 16
TCACHE_TILE_BYTES      = TCACHE_TILE_TEXELS * TEXEL_BYTES   # 64 B
TCACHE_NUM_TILES       = 512
TCACHE_QUADS_PER_CYCLE = 4

# ─────────────────────────────────────────────────────────────
# Workload generators
# ─────────────────────────────────────────────────────────────

def clamp(v, lo, hi): return max(lo, min(hi, v))

def bilinear_quad(tx: float, ty: float) -> List[Tuple[int,int]]:
    """Return the 4 integer texel coords for a bilinear sample at (tx,ty)."""
    x0 = clamp(int(tx), 0, TEX_W - 2)
    y0 = clamp(int(ty), 0, TEX_H - 2)
    return [(x0, y0), (x0+1, y0), (x0, y0+1), (x0+1, y0+1)]

def workload_1x_map(screen_w=128, screen_h=128) -> List[List[Tuple[int,int]]]:
    """Full-screen quad, UV = pixel position. Smooth 1:1 scan — best-case locality."""
    quads = []
    for fy in range(0, screen_h, 2):
        for fx in range(0, screen_w, 2):
            for dfy in range(2):
                for dfx in range(2):
                    u = (fx + dfx) / screen_w * (TEX_W - 1)
                    v = (fy + dfy) / screen_h * (TEX_H - 1)
                    quads.append(bilinear_quad(u, v))
    return quads

def workload_perspective(screen_w=128, screen_h=128) -> List[List[Tuple[int,int]]]:
    """Perspective-foreshortened quad: V compresses quadratically toward horizon."""
    quads = []
    for fy in range(0, screen_h, 2):
        for fx in range(0, screen_w, 2):
            for dfy in range(2):
                for dfx in range(2):
                    nx = (fx + dfx) / screen_w
                    ny = (fy + dfy) / screen_h
                    u = (0.1 + 0.8 * nx) * (TEX_W - 1)
                    v = (ny * ny) * (TEX_H - 1)
                    quads.append(bilinear_quad(u, v))
    return quads

def workload_minified(screen_w=32, screen_h=32, scale=4.0) -> List[List[Tuple[int,int]]]:
    """Small screen over full texture — large UV stride, poor locality."""
    quads = []
    for fy in range(0, screen_h, 2):
        for fx in range(0, screen_w, 2):
            for dfy in range(2):
                for dfx in range(2):
                    u = clamp((fx + dfx) * scale, 0, TEX_W - 2)
                    v = clamp((fy + dfy) * scale, 0, TEX_H - 2)
                    quads.append(bilinear_quad(u, v))
    return quads

# ─────────────────────────────────────────────────────────────
# D-Cache  (LRU, 128B lines)
#
# Throughput: 1 cache-line per cycle (not 1 texel).
# Useful-byte accounting: SET of unique (x,y) texels touched per line
# so bandwidth efficiency is capped at 100%.
# ─────────────────────────────────────────────────────────────

class DCache:
    def __init__(self):
        self.tags:       Dict[int, int] = {}
        self.unique_use: Dict[int, Set] = defaultdict(set)
        self.ts = 0

        self.total_requests   = 0
        self.line_accesses    = 0
        self.hits             = 0
        self.misses           = 0
        self.bytes_fetched    = 0
        self.useful_bytes     = 0
        self.mem_transactions = 0
        self.redundant_texels = 0

        self._last_tag        = None

    def _tag(self, x, y):
        return morton_encode(x, y) // DCACHE_LINE_TEXELS

    def _evict(self, tag):
        used = len(self.unique_use.pop(tag, set()))
        self.useful_bytes    += used * TEXEL_BYTES
        waste = DCACHE_LINE_TEXELS - used
        if waste > 0:
            self.redundant_texels += waste
        del self.tags[tag]

    def access(self, x, y):
        self.total_requests += 1
        tag = self._tag(x, y)

        if tag != self._last_tag:
            self.line_accesses += 1
            self._last_tag = tag

        if tag in self.tags:
            self.hits += 1
            self.tags[tag] = self.ts; self.ts += 1
        else:
            self.misses += 1
            self.bytes_fetched    += DCACHE_LINE_BYTES
            self.mem_transactions += 1
            if len(self.tags) >= DCACHE_NUM_LINES:
                evict = min(self.tags, key=lambda t: self.tags[t])
                self._evict(evict)
            self.tags[tag] = self.ts; self.ts += 1

        self.unique_use[tag].add((x, y))

    def flush(self):
        for tag in list(self.tags):
            self._evict(tag)

    @property
    def miss_rate(self):
        return self.misses / self.total_requests if self.total_requests else 0

    @property
    def useful_pct(self):
        return self.useful_bytes / self.bytes_fetched * 100 if self.bytes_fetched else 0

    @property
    def total_cycles(self):
        return self.line_accesses

    @property
    def throughput(self):
        return self.total_requests / self.total_cycles if self.total_cycles else 0


# ─────────────────────────────────────────────────────────────
# T-Cache  (LRU, 2x2 tile granularity, 16 banks)
# ─────────────────────────────────────────────────────────────

class TCache:
    def __init__(self):
        self.tiles: Dict[int, int] = {}
        self.ts = 0

        self.total_requests   = 0
        self.hits             = 0
        self.misses           = 0
        self.bytes_fetched    = 0
        self.useful_bytes     = 0
        self.mem_transactions = 0
        self.redundant_texels = 0
        self._quad_count      = 0

    def _tile_tag(self, x, y):
        return morton_encode(x // TCACHE_TILE_W, y // TCACHE_TILE_H)

    def access_quad(self, texels: List[Tuple[int,int]]):
        assert len(texels) == 4
        self.total_requests += 4
        self._quad_count    += 1
        tag = self._tile_tag(texels[0][0], texels[0][1])

        if tag in self.tiles:
            self.hits += 4
            self.tiles[tag] = self.ts; self.ts += 1
        else:
            self.misses += 4
            self.bytes_fetched    += TCACHE_TILE_BYTES
            self.useful_bytes     += TCACHE_TILE_BYTES
            self.mem_transactions += 1
            if len(self.tiles) >= TCACHE_NUM_TILES:
                evict = min(self.tiles, key=lambda t: self.tiles[t])
                del self.tiles[evict]
            self.tiles[tag] = self.ts; self.ts += 1

    @property
    def miss_rate(self):
        return self.misses / self.total_requests if self.total_requests else 0

    @property
    def useful_pct(self):
        return self.useful_bytes / self.bytes_fetched * 100 if self.bytes_fetched else 0

    @property
    def total_cycles(self):
        return math.ceil(self._quad_count / TCACHE_QUADS_PER_CYCLE)

    @property
    def throughput(self):
        return self.total_requests / self.total_cycles if self.total_cycles else 0


# ─────────────────────────────────────────────────────────────
# Runner — prints table AND returns stats dict for graphing
# ─────────────────────────────────────────────────────────────

def run_workload(name: str, quads: List[List[Tuple[int,int]]]) -> dict:
    dc = DCache()
    tc = TCache()

    for quad in quads:
        for (x, y) in quad:
            dc.access(x, y)
        tc.access_quad(quad)
    dc.flush()

    def pct(a, b): return f"{100*a/b:5.1f}%" if b else "  N/A "
    def fmt(n):    return f"{n:>13,}"

    print(f"\n+{'-'*66}+")
    print(f"| Workload: {name:<56}|")
    print(f"| Quads simulated: {len(quads):<49}|")
    print(f"+{'-'*36}+{'-'*14}+{'-'*14}+")
    print(f"| {'Metric':<35}| {'D-Cache':>12}  | {'T-Cache':>12}  |")
    print(f"+{'-'*36}+{'-'*14}+{'-'*14}+")

    speedup = dc.total_cycles / tc.total_cycles if tc.total_cycles else 0

    rows = [
        ("Total texel requests",          fmt(dc.total_requests),      fmt(tc.total_requests)),
        ("Cache misses (texels)",          fmt(dc.misses),              fmt(tc.misses)),
        ("Miss rate",                      pct(dc.misses, dc.total_requests),
                                           pct(tc.misses, tc.total_requests)),
        ("Memory transactions",            fmt(dc.mem_transactions),    fmt(tc.mem_transactions)),
        ("Bytes fetched from memory",      fmt(dc.bytes_fetched),       fmt(tc.bytes_fetched)),
        ("Useful bytes consumed",          fmt(dc.useful_bytes),        fmt(tc.useful_bytes)),
        ("% Useful reads (BW eff.)",       pct(dc.useful_bytes, dc.bytes_fetched),
                                           pct(tc.useful_bytes, tc.bytes_fetched)),
        ("Redundant texels fetched",       fmt(dc.redundant_texels),    fmt(tc.redundant_texels)),
        ("Total processing cycles",        fmt(dc.total_cycles),        fmt(tc.total_cycles)),
        ("Throughput (texels/cycle)",      f"{dc.throughput:>13.2f}",   f"{tc.throughput:>13.2f}"),
        ("Cycle speedup  (T-Cache / D)",   "",                          f"{speedup:>12.1f}x"),
    ]
    for label, dv, tv in rows:
        print(f"| {label:<35}| {dv:>13} | {tv:>13} |")

    print(f"+{'-'*36}+{'-'*14}+{'-'*14}+")

    wasted_dc = dc.bytes_fetched - dc.useful_bytes
    wasted_tc = tc.bytes_fetched - tc.useful_bytes
    if wasted_tc == 0 and wasted_dc > 0:
        print(f"  Wasted BW -> D-Cache: {wasted_dc:,} B  |  T-Cache: 0 B")
    elif wasted_dc > 0:
        ratio = wasted_dc / max(wasted_tc, 1)
        print(f"  Wasted BW -> D-Cache: {wasted_dc:,} B  |  "
              f"T-Cache: {wasted_tc:,} B  (ratio {ratio:.1f}x)")

    # Return stats dict for make_graphs()
    return dict(
        name          = name,
        miss_rate_dc  = dc.miss_rate * 100,
        miss_rate_tc  = tc.miss_rate * 100,
        useful_pct_dc = dc.useful_pct,
        useful_pct_tc = tc.useful_pct,
        cycles_dc     = dc.total_cycles,
        cycles_tc     = tc.total_cycles,
        throughput_dc = dc.throughput,
        throughput_tc = tc.throughput,
        redundant_dc  = dc.redundant_texels,
        redundant_tc  = tc.redundant_texels,
        bytes_dc      = dc.bytes_fetched,
        bytes_tc      = tc.bytes_fetched,
        mem_tx_dc     = dc.mem_transactions,
        mem_tx_tc     = tc.mem_transactions,
    )


# ─────────────────────────────────────────────────────────────
# Graphing
# ─────────────────────────────────────────────────────────────

def make_graphs(results: List[dict]):
    DC   = '#E05C4B'
    TC   = '#4B8FE0'
    BG   = '#0F1117'
    FG   = '#E8E6DF'
    GRID = '#2A2D38'
    AX   = '#1A1D27'

    short     = ['1:1 Map', 'Perspective', 'Minified 4x']

    miss_dc   = [r['miss_rate_dc']  for r in results]
    miss_tc   = [r['miss_rate_tc']  for r in results]
    bw_dc     = [r['useful_pct_dc'] for r in results]
    bw_tc     = [r['useful_pct_tc'] for r in results]
    cyc_dc    = [r['cycles_dc']     for r in results]
    cyc_tc    = [r['cycles_tc']     for r in results]
    tput_dc   = [r['throughput_dc'] for r in results]
    tput_tc   = [r['throughput_tc'] for r in results]
    redund_dc = [r['redundant_dc']  for r in results]
    redund_tc = [r['redundant_tc']  for r in results]
    bytes_dc  = [r['bytes_dc']/1024 for r in results]
    bytes_tc  = [r['bytes_tc']/1024 for r in results]

    x = np.arange(len(short))
    w = 0.35

    plt.rcParams.update({
        'figure.facecolor':  BG,
        'axes.facecolor':    AX,
        'axes.edgecolor':    GRID,
        'axes.labelcolor':   FG,
        'axes.titlecolor':   FG,
        'xtick.color':       FG,
        'ytick.color':       FG,
        'grid.color':        GRID,
        'text.color':        FG,
        'font.family':       'monospace',
        'axes.spines.top':   False,
        'axes.spines.right': False,
    })

    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    fig.suptitle('D-Cache vs T-Cache  —  Texture Access Comparison',
                 fontsize=15, fontweight='bold', color=FG, y=0.98)

    def bar_ax(ax, title, dc_vals, tc_vals, ylabel, pct=False):
        b1 = ax.bar(x - w/2, dc_vals, w, label='D-Cache', color=DC, alpha=0.9, zorder=3)
        b2 = ax.bar(x + w/2, tc_vals, w, label='T-Cache', color=TC, alpha=0.9, zorder=3)
        ax.set_title(title, fontsize=11, pad=8)
        ax.set_ylabel(ylabel, fontsize=9)
        ax.set_xticks(x)
        ax.set_xticklabels(short, fontsize=9)
        ax.grid(axis='y', zorder=0, linewidth=0.5)
        ax.legend(fontsize=8, framealpha=0.3)
        for bar in list(b1) + list(b2):
            h = bar.get_height()
            label = f'{h:.1f}%' if pct else (f'{h:.1f}' if h < 1000 else f'{h/1000:.1f}k')
            ax.text(bar.get_x() + bar.get_width()/2,
                    h + max(dc_vals + tc_vals) * 0.01,
                    label, ha='center', va='bottom', fontsize=7.5, color=FG)

    # [1] Miss rate
    bar_ax(axes[0,0], '[1] Miss Rate (%)',
           miss_dc, miss_tc, 'Miss rate (%)', pct=True)
    axes[0,0].set_ylim(0, max(miss_dc + miss_tc) * 1.25)

    # [2] Bandwidth efficiency
    bar_ax(axes[0,1], '[2] % Useful Reads (Bandwidth Efficiency)',
           bw_dc, bw_tc, 'Useful bytes / fetched bytes (%)', pct=True)
    axes[0,1].set_ylim(0, 115)
    axes[0,1].axhline(100, color=FG, linewidth=0.8, linestyle='--', alpha=0.4, zorder=2)
    axes[0,1].text(2.55, 101, '100% ideal', fontsize=7, color=FG, alpha=0.5)

    # [3] Processing cycles
    bar_ax(axes[0,2], '[3] Total Processing Cycles',
           cyc_dc, cyc_tc, 'Cycles')

    # [4] Throughput
    bar_ax(axes[1,0], '[4] Throughput (texels / cycle)',
           tput_dc, tput_tc, 'texels / cycle')

    # [5] Redundant texels
    bar_ax(axes[1,1], '[5] Redundant Texels Fetched (wasted BW)',
           redund_dc, redund_tc, 'Texels fetched but never used')

    # [6] Bytes fetched from memory
    bar_ax(axes[1,2], '[6] Bytes Fetched from Memory (KB)',
           bytes_dc, bytes_tc, 'KB fetched from DRAM')

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig('cache_comparison.png', dpi=150, bbox_inches='tight', facecolor=BG)
    plt.close()
    print('Graph saved -> cache_comparison.png')


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main():
    print("=" * 68)
    print("   D-CACHE vs T-CACHE  --  Texture Access Simulation")
    print(f"   Texture : {TEX_W}x{TEX_H} RGBA8  |  Morton-ordered storage")
    print(f"   D-Cache : {DCACHE_NUM_LINES} lines x {DCACHE_LINE_BYTES}B "
          f"({DCACHE_LINE_TEXELS} texels/line) | 1 line/cycle throughput")
    print(f"   T-Cache : {TCACHE_NUM_TILES} tiles x {TCACHE_TILE_BYTES}B "
          f"({TCACHE_TILE_TEXELS} texels/tile) | {TCACHE_QUADS_PER_CYCLE} quads/cycle (16 banks)")
    print("=" * 68)

    workloads = [
        ("1:1 Magnified mapping  (best-case locality)",
         workload_1x_map(128, 128)),
        ("Perspective warp  (non-uniform UV, mixed locality)",
         workload_perspective(128, 128)),
        ("Minification 4x  (large texel stride, poor locality)",
         workload_minified(32, 32, scale=4.0)),
    ]

    results = []
    for name, quads in workloads:
        results.append(run_workload(name, quads))

    make_graphs(results)


if __name__ == "__main__":
    main()