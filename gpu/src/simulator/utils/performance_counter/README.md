# Performance Counter & Tracing Framework

Telemetry framework for the GPU simulator. Collects per-cycle summary statistics
and optional cycle-level trace rows, exported to Parquet for analysis in VisiData
or any Polars-aware tool.

All framework code lives in this directory:

```
utils/performance_counter/
    __init__.py            # public API — import everything from here
    perf_counter_base.py   # PerfCounterBase ABC
    perf_config.py         # SnapshotScope, TriggerOperator, TriggerConfig,
                           # FlightRecorderConfig, PerfConfig
    telemeter.py           # Telemeter (central provider)
```

---

## Table of Contents

1. [Creating a PerfCounter subclass](#1-creating-a-perfcounter-subclass)
2. [Wiring a unit into the Telemeter](#2-wiring-a-unit-into-the-telemeter)
3. [Configuring PerfConfig](#3-configuring-perfconfig)
4. [Flight Recorder and Triggers](#4-flight-recorder-and-triggers)
5. [Snapshot providers — Register File, Memory, and Caches](#5-snapshot-providers--register-file-memory-and-caches)
6. [Main simulation loop integration](#6-main-simulation-loop-integration)
7. [Output files](#7-output-files)
8. [Viewing Parquet files](#8-viewing-parquet-files)

---

## 1. Creating a PerfCounter subclass

Every pipeline unit that needs telemetry gets its own `PerfCounterBase` subclass.
The base class already handles `total_cycles`, `stall_cycles`, `busy_cycles`,
`idle_cycles`, and the derived rates.  You only need to override two optional hooks.

### Step 1 — Subclass and declare custom counters

```python
# e.g. gpu/simulator/src/execute/perf_count.py

from simulator.utils.performance_counter import PerfCounterBase


class ExecutePerfCount(PerfCounterBase):
    def __init__(self, name: str) -> None:
        super().__init__(name)

        # Unit-specific accumulators — add whatever you need.
        self.cache_miss_cycles: int = 0
        self.pipeline_full_cycles: int = 0
        self.overflow_cycles: int = 0
```

### Step 2 — Override `_record_unit_cycle`

Called automatically every cycle by `record_cycle()`, with all of its
keyword arguments forwarded through.  Use keyword-only args with defaults
so the base class can call this without knowing your field names.

```python
    def _record_unit_cycle(
        self,
        *,
        cache_miss: bool = False,
        pipeline_full: bool = False,
        overflow: bool = False,
        **kwargs,          # absorb any other kwargs you don't care about
    ) -> None:
        if cache_miss:
            self.cache_miss_cycles += 1
        if pipeline_full:
            self.pipeline_full_cycles += 1
        if overflow:
            self.overflow_cycles += 1
```

### Step 3 — Override `_extra_summary`

Return a flat `dict` of derived stats.  These are merged into the row written
to `perf_summary.parquet`.  Use `self._safe_div()` for rates — it returns `0.0`
instead of raising `ZeroDivisionError`.

```python
    def _extra_summary(self) -> dict:
        return {
            "cache_miss_cycles":   self.cache_miss_cycles,
            "cache_miss_rate":     self._safe_div(self.cache_miss_cycles, self.total_cycles),
            "pipeline_full_cycles": self.pipeline_full_cycles,
            "pipeline_full_rate":  self._safe_div(self.pipeline_full_cycles, self.total_cycles),
            "overflow_cycles":     self.overflow_cycles,
        }
```

### Step 4 — (optional) Override `_reset_unit_counters`

Only needed if you want to support mid-run resets (e.g. between kernel launches).

```python
    def _reset_unit_counters(self) -> None:
        self.cache_miss_cycles = 0
        self.pipeline_full_cycles = 0
        self.overflow_cycles = 0
```

---

## 2. Wiring a unit into the Telemeter

### Add the counter and Telemeter to your unit's `__init__`

```python
from simulator.utils.performance_counter import PerfCounterBase, Telemeter
from simulator.execute.perf_count import ExecutePerfCount


class FunctionalSubUnit:
    def __init__(self, num: int, telemeter: Telemeter) -> None:
        self.name = f"{self.__class__.__name__}_{num}"
        self.telemeter = telemeter

        # Create and register the counter — the Telemeter sets .enabled
        # automatically based on PerfConfig.enabled_units.
        self.perf_count = ExecutePerfCount(name=self.name)
        telemeter.register_unit(self.perf_count)
```

### Add telemetry calls to `tick()`

```python
    def tick(self, cycle: int) -> None:
        # ---- simulation logic ----
        stalled      = ...
        busy         = ...
        cache_miss   = ...
        pipeline_full = ...

        # 1. Summary counters (always; no-op when unit is disabled in config)
        self.perf_count.record_cycle(
            is_stalled    = stalled,
            is_busy       = busy,
            cache_miss    = cache_miss,
            pipeline_full = pipeline_full,
        )

        # 2. Cycle-level trace (guard avoids dict allocation on inactive cycles)
        if self.telemeter.is_trace_active(cycle):
            self.telemeter.record_trace(
                cycle, self.name,
                warp_id       = warp_id,
                is_stalled    = stalled,
                cache_miss    = cache_miss,
                pipeline_full = pipeline_full,
            )

        # 3. Flight recorder trigger evaluation
        self.telemeter.check_triggers(
            self.name, cycle,
            is_stalled    = stalled,
            cache_miss    = cache_miss,
            pipeline_full = pipeline_full,
        )
```

> **Rule:** Always call `is_trace_active(cycle)` before `record_trace()`.
> This avoids building the `dict` on cycles where tracing is not active,
> which is the dominant hot-path cost.

---

## 3. Configuring PerfConfig

Create one `PerfConfig` instance and pass it to the `Telemeter` constructor.

```python
from simulator.utils.performance_counter import (
    PerfConfig, FlightRecorderConfig, TriggerConfig, TriggerOperator,
)

# --- Minimal: summary counters only, no traces ---
config = PerfConfig.summary_only()

# --- Range tracing (no flight recorder) ---
config = PerfConfig.full_trace(start=1000, end=5000)

# --- Selective units + range tracing ---
config = PerfConfig.full_trace(
    start         = 1000,
    end           = 5000,
    enabled_units = {"ALU_Int_0", "ALU_Float_0", "ICacheStage"},
    buffer_limit  = 100_000,   # rows before an auto-flush to disk
)

# --- Completely disabled (zero overhead) ---
config = PerfConfig.disabled()
```

### `enabled_units` semantics

| Value | Effect |
|---|---|
| `set()` (empty, default) | All registered units are enabled |
| `{"ALU_Int_0", "L1"}` | Only listed units active; others are no-ops |

### `trace_range`

`(0, 0)` disables cycle-level traces entirely while still collecting summary
counters.  Summary counters always run while the unit is enabled.

---

## 4. Flight Recorder and Triggers

The flight recorder captures a configurable window of trace rows around a
trigger condition.  Every trigger maintains its own criteria for what fires it
and what gets captured.

### Concepts

| Term | Meaning |
|---|---|
| **Pre-capture deque** | Circular buffer of the last N trace rows before the trigger fires |
| **`watched_units`** | Which unit names can fire this trigger (empty = any) |
| **`capture_units`** | Which unit trace rows to save in the capture window (empty = all) |
| **`pre_capture_depth`** | How many rows of history to keep before the trigger (default 64) |
| **`post_capture_cycles`** | How many cycles to capture after the trigger fires (default 32) |

### Defining triggers

```python
from simulator.utils.performance_counter import (
    PerfConfig, FlightRecorderConfig, TriggerConfig, TriggerOperator,
)

config = PerfConfig.full_trace(
    start = 0,
    end   = 1_000_000,
    flight_recorder = FlightRecorderConfig(
        triggers=[

            # Trigger 1: any ALU stall
            TriggerConfig(
                name               = "alu_stall",
                field              = "is_stalled",
                operator           = TriggerOperator.EQ,
                value              = True,
                watched_units      = {"ALU_Int_0", "ALU_Float_0"},  # who can FIRE
                capture_units      = {"ALU_Int_0", "ALU_Float_0", "Decode_Stage"},  # who gets CAPTURED
                pre_capture_depth  = 64,
                post_capture_cycles= 32,
            ),

            # Trigger 2: I-cache miss
            TriggerConfig(
                name               = "icache_miss",
                field              = "cache_miss",
                operator           = TriggerOperator.EQ,
                value              = True,
                watched_units      = {"ICacheStage"},
                pre_capture_depth  = 16,
                post_capture_cycles= 8,
            ),

            # Trigger 3: buffer occupancy exceeds threshold
            TriggerConfig(
                name               = "writeback_pressure",
                field              = "buffer_occupancy",
                operator           = TriggerOperator.GTE,
                value              = 24,
                watched_units      = {"WritebackStage"},
            ),

        ]
    ),
)
```

### Available `TriggerOperator` values

| Operator | Condition |
|---|---|
| `EQ` | `field == value` |
| `NE` | `field != value` |
| `GT` | `field > value` |
| `GTE` | `field >= value` |
| `LT` | `field < value` |
| `LTE` | `field <= value` |

### Multi-trigger simultaneous firing semantics

When multiple triggers fire on the same cycle:
- The **longest** `post_capture_cycles` window takes effect.
- `capture_units` are **unioned** (empty on any trigger → capture all).
- Snapshot scopes are **unioned per provider** — the broader scope wins.
  An empty (unbounded) scope always overrides a bounded one.

---

## 5. Snapshot providers — Register File, Memory, and Caches

Snapshot providers allow you to capture the full state of the register file,
memory, or caches when a trigger fires.  They are callables registered with
the `Telemeter` after simulation objects are constructed.

### Provider signature

```python
def my_provider(scope: Optional[SnapshotScope]) -> Dict[str, Any]:
    ...
```

- `scope=None` means **full snapshot** — return everything.
- A `SnapshotScope` restricts which warps/threads/addresses to return.
- The returned `dict` keys become Parquet column names in `traces.parquet`.
  Use `snake_case`.

### Registering providers

Call `register_snapshot_provider()` **after** the `Telemeter` is constructed
and simulation objects exist, but **before** the simulation loop starts.

```python
telemeter = Telemeter(config=config, output_dir="perf_out")

# Wire simulation objects
reg_file   = RegisterFile(banks=2, warps=32, ...)
memory     = Mem(start_pc=0x0, input_file="program.bin")
icache     = ICacheStage(...)
dcache     = ...   # your data cache

# --- Register File provider ---
def rf_snapshot(scope):
    rows = {}
    warps_to_snap = range(reg_file.warps) if (scope is None or scope.all_warps()) \
                    else scope.warps
    threads_to_snap = range(reg_file.threads_per_warp) if (scope is None or scope.all_threads()) \
                      else scope.threads
    for warp in warps_to_snap:
        for thread in threads_to_snap:
            for reg in range(reg_file.regs_per_warp):
                rows[f"w{warp}_t{thread}_r{reg}"] = \
                    reg_file.read_thread_gran(warp, reg, thread)
    return rows

telemeter.register_snapshot_provider("register_file", rf_snapshot)

# --- Data Memory provider ---
def mem_snapshot(scope):
    if scope is None or scope.all_addresses():
        return {f"mem_{addr:#010x}": val for addr, val in memory.memory.items()}
    return {
        f"mem_{addr:#010x}": memory.memory.get(addr, 0)
        for addr in scope.addresses
    }

telemeter.register_snapshot_provider("memory", mem_snapshot)

# --- I-Cache provider ---
def icache_snapshot(scope):
    result = {}
    for set_idx, ways in icache.cache.items():
        for way_idx, entry in enumerate(ways):
            if not entry.valid:
                continue
            line_addr = entry.tag  # adapt to your actual address reconstruction
            if scope is not None and not scope.all_icache_addresses():
                if line_addr not in scope.icache_addresses:
                    continue
            result[f"icache_set{set_idx}_way{way_idx}_tag"] = entry.tag
            result[f"icache_set{set_idx}_way{way_idx}_valid"] = entry.valid
    return result

telemeter.register_snapshot_provider("icache", icache_snapshot)

# --- D-Cache provider (same pattern) ---
def dcache_snapshot(scope):
    result = {}
    # ... iterate dcache.cache, filter by scope.dcache_addresses ...
    return result

telemeter.register_snapshot_provider("dcache", dcache_snapshot)
```

### Attaching providers to triggers with `SnapshotScope`

```python
from simulator.utils.performance_counter import SnapshotScope

TriggerConfig(
    field              = "is_stalled",
    operator           = TriggerOperator.EQ,
    value              = True,
    watched_units      = {"ALU_Int_0"},
    snapshot_providers = {"register_file", "memory", "icache", "dcache"},
    snapshot_scopes    = {
        # RF — only warps 0–3, thread 0
        "register_file": SnapshotScope(warps={0, 1, 2, 3}, threads={0}),

        # Data memory — only these two addresses
        "memory": SnapshotScope(addresses={0x1000, 0x1004}),

        # I-cache — only lines covering the stalled PC
        "icache": SnapshotScope(icache_addresses={0x0080, 0x0084}),

        # D-cache — only these cache line addresses
        "dcache": SnapshotScope(dcache_addresses={0x4000, 0x4040}),

        # "memory" not listed here → full memory snapshot when it fires
    },
    snapshot_each_cycle = False,   # True = snapshot every post-capture cycle (expensive)
    post_capture_cycles = 16,
)
```

#### `SnapshotScope` field summary

| Field | Filters | Empty means |
|---|---|---|
| `warps` | Register file warps | All warps |
| `threads` | Threads within each warp | All threads |
| `addresses` | Data memory addresses | All addresses |
| `icache_addresses` | I-cache line addresses (PCs) | All I-cache lines |
| `dcache_addresses` | D-cache line addresses | All D-cache lines |

All fields accept plain Python `int` values — use hex literals for readability:
```python
SnapshotScope(icache_addresses={0x0080, 0x0084}, dcache_addresses={0x4000})
```

---

## 6. Main simulation loop integration

```python
telemeter = Telemeter(config=config, output_dir="perf_out")

# ... construct all units, register providers ...

for cycle in range(total_cycles):
    telemeter.advance_flight_recorder(cycle)   # MUST be first — manages post-capture window
    # ... tick all units ...

telemeter.finalize()   # flush buffers, combine Parquet parts, write summaries
```

`advance_flight_recorder(cycle)` must be called **once per simulation cycle**
at the top of the loop.  It decrements the post-capture counter, handles
per-cycle snapshots if `snapshot_each_cycle=True`, and clears trigger state
when the window closes.

`finalize()` is called **once** after the loop exits.  It:
1. Flushes any remaining trace rows to a part file.
2. Combines all `traces_part_NNNN.parquet` files into a single `traces.parquet`
   and deletes the parts.
3. Writes `trigger_summary.parquet` (if a flight recorder is configured).
4. Collects `finalize()` from all registered `PerfCounterBase` instances and
   writes `perf_summary.parquet`.

---

## 7. Output files

| File | Contents |
|---|---|
| `perf_out/perf_summary.parquet` | One row per unit: all base and unit-specific counters + derived rates |
| `perf_out/traces.parquet` | All cycle-level trace rows, combined at `finalize()` |
| `perf_out/trigger_summary.parquet` | Trigger config and fire-event history (see below) |
| `perf_out/traces_part_NNNN.parquet` | Intermediate flush files — deleted by `finalize()` |

### `trigger_summary.parquet` schema

Contains two interleaved `row_type` values:

| `row_type` | One row per | Runtime columns populated? |
|---|---|---|
| `"config"` | Registered `TriggerConfig` | No (`null`) |
| `"event"` | Each time a trigger fires | Yes |

Runtime columns on `"event"` rows:

| Column | Type | Description |
|---|---|---|
| `fired_cycle` | `Int64` | Cycle on which the trigger fired |
| `fired_by_unit` | `Utf8` | Unit name that caused the fire |
| `pre_capture_rows` | `Int64` | Rows committed from the pre-capture deque |
| `pre_capture_start_cycle` | `Int64` | Earliest cycle in the committed pre-capture rows |
| `post_capture_end_cycle` | `Int64` | `fired_cycle + post_capture_cycles` |

Config columns present on every row (both `"config"` and `"event"`):
`trigger_name`, `trigger_field`, `trigger_operator`, `trigger_value`,
`watched_units`, `capture_units`, `pre_capture_depth`, `post_capture_cycles`,
`snapshot_providers`, `snapshot_scopes`, `snapshot_each_cycle`.

---

## 8. Viewing Parquet files

### Data Wrangler (VS Code extension) — recommended

Data Wrangler is a VS Code extension that provides a spreadsheet-style view of
Parquet files with built-in filtering, sorting, and summary statistics.  It works
over SSH remote connections (VS Code Remote — SSH) without copying files locally.

**Install once:**

1. Open the Extensions panel (`Ctrl+Shift+X`).
2. Search for **Data Wrangler** (publisher: Microsoft).
3. Click **Install**.  The extension installs on the remote host automatically
   when connected via Remote — SSH.

**Opening a Parquet file:**

- In the Explorer panel, right-click any `.parquet` file and choose
  **Open in Data Wrangler**.
- Or open the file normally and click the **Open in Data Wrangler** button
  that appears in the editor toolbar.

**Key features:**

| Feature | How to use |
|---|---|
| Column summary | Click any column header to see min, max, mean, null count, and a histogram |
| Filter rows | Click the **Filter** icon in the toolbar; write a Python expression, e.g. `unit_name == "ALU_Int_0"` |
| Sort | Click a column header once (ascending) or twice (descending) |
| Search | `Ctrl+F` within the grid |
| Export to CSV | **File → Export** from the Data Wrangler toolbar |
| View a column's unique values | Right-click a column → **View unique values** |

**Typical workflow for GPU trace analysis:**

1. Run the simulation — `finalize()` writes `perf_out/perf_summary.parquet`,
   `perf_out/traces.parquet`, and `perf_out/trigger_summary.parquet`.
2. In VS Code Explorer, open `perf_summary.parquet` in Data Wrangler to get a
   quick overview of stall rates and utilization across all units.
3. Open `trigger_summary.parquet` and filter to `row_type == "event"` to see
   every trigger fire with its cycle range and pre-capture depth.
4. Open `traces.parquet`, filter to the `unit_name` and cycle range reported by
   a trigger event, and inspect the per-cycle field values around the event.

> **Note:** Data Wrangler loads the full Parquet file into memory.  For very
> large `traces.parquet` files (> ~500 MB) prefer the Polars or DuckDB approach
> below, or pre-filter using Polars and save a smaller slice first:
> ```python
> import polars as pl
> pl.read_parquet("perf_out/traces.parquet") \
>   .filter(pl.col("cycle").is_between(1000, 2000)) \
>   .write_parquet("perf_out/traces_slice.parquet")
> ```
> Then open `traces_slice.parquet` in Data Wrangler.

### VisiData (terminal / SSH fallback)

VisiData is a terminal spreadsheet viewer — useful when VS Code is unavailable
or when working in a plain SSH session.

```bash
# Install
pip install visidata pyarrow

# Open any output file
vd perf_out/perf_summary.parquet
vd perf_out/traces.parquet
vd perf_out/trigger_summary.parquet

# Key bindings inside VisiData
# F      — frequency table for current column
# [  ]   — sort ascending / descending
# /      — search
# =      — add derived column (Python expression)
# ^S     — save to CSV or another format
```

### Polars (in Python / Jupyter)

```python
import polars as pl

# Summary stats for all units
df = pl.read_parquet("perf_out/perf_summary.parquet")
print(df.select(["unit_name", "total_cycles", "stall_rate", "utilization_rate"]))

# All trace rows
traces = pl.read_parquet("perf_out/traces.parquet")

# Filter to a specific unit and cycle range
alu_traces = traces.filter(
    (pl.col("unit_name") == "ALU_Int_0") &
    (pl.col("cycle").is_between(1000, 2000))
)

# Trigger history — all fires of "alu_stall"
trig = pl.read_parquet("perf_out/trigger_summary.parquet")
fires = trig.filter(
    (pl.col("row_type") == "event") &
    (pl.col("trigger_name") == "alu_stall")
)
print(fires.select(["fired_cycle", "fired_by_unit", "pre_capture_rows", "post_capture_end_cycle"]))

# Read part files during a run (before finalize())
from pathlib import Path
parts = sorted(Path("perf_out").glob("traces_part_*.parquet"))
live = pl.read_parquet(parts, allow_missing_columns=True)
```

### DuckDB (SQL over Parquet)

```python
import duckdb

duckdb.sql("SELECT unit_name, stall_rate FROM 'perf_out/perf_summary.parquet' ORDER BY stall_rate DESC")
duckdb.sql("SELECT * FROM 'perf_out/traces.parquet' WHERE unit_name = 'ICacheStage' AND cache_miss = true LIMIT 100")
```
