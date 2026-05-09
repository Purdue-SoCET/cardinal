# Instructions for Copilot: Performance Counter & Tracing Framework

## **Project Context**

You are helping build a **Performance Counter & Tracing Framework** for a cycle-accurate GPU simulator written in Python. The framework must handle high-volume telemetry (millions of cycles) with minimal simulation overhead. Data is exported to **Parquet** for analysis in **VisiData** over SSH.

---

## **Module Location**

All framework code lives under:

```
gpu/simulator/src/utils/performance_counter/
    __init__.py            # exports all public classes
    perf_counter_base.py   # PerfCounterBase ABC
    perf_config.py         # SnapshotScope, TriggerOperator, TriggerConfig,
                           # FlightRecorderConfig, PerfConfig
    telemeter.py           # Telemeter (central provider)
```

Public API (importable from `simulator.utils.performance_counter`):
`PerfCounterBase`, `PerfConfig`, `FlightRecorderConfig`, `TriggerConfig`,
`TriggerOperator`, `SnapshotScope`, `Telemeter`

---

## **Core Architectural Principles**

1. **De-coupled Telemetry:** Simulation logic must not couple with data collection. The `Telemeter` is passed explicitly to every module — no global state.
2. **Performance First:** The hot-path check is a single `if not self.enabled: return` in `record_cycle()` and `if self.telemeter.is_trace_active(cycle):` in `tick()`. Disabled units impose near-zero overhead.
3. **Columnar Data:** All trace rows are `Dict[str, Any]`; keys become Parquet column names. Use snake_case. Prefer wide tables (e.g., `thread_0_pc`, `thread_1_pc`) for warp data.
4. **Sequential → Parallel Path:** Avoid global state. Pass `Telemeter` instances explicitly so multiprocessing can be added later.
5. **Ease of Use:** Concrete unit counters subclass `PerfCounterBase` and override two optional hooks. No knowledge of Parquet or Polars required.

---

## **Technical Standards**

* **Data Engine:** Use **Polars** (`pl.DataFrame`) for all data manipulation and Parquet I/O. **Never use Pandas.**
* **Buffering:** `List[Dict]` trace buffer. Flush with `pl.from_dicts(buffer).write_parquet(path)` when `len(buffer) >= PerfConfig.buffer_limit`.
* **Multi-Part Parquet:** Each `flush_traces()` call writes a new `traces_part_NNNN.parquet`. `finalize()` combines all parts via `pl.read_parquet([...], allow_missing_columns=True)` then deletes the parts. **Never read-back-concat-rewrite** a single file (O(n²) cost).
* **Type Hinting:** Strict Python type hints on all public methods.
* **Python Version:** Python 3.12+. `match`/`case` is used in `TriggerConfig.evaluate()`.

---

## **Class Reference**

### `PerfCounterBase` (ABC) — `perf_counter_base.py`

Abstract base class for all per-unit performance counters.

**Built-in accumulators** (updated automatically by `record_cycle()`):
- `total_cycles`, `stall_cycles`, `busy_cycles`, `idle_cycles`

**Derived stats** (computed by `finalize()`):
- `stall_rate`, `utilization_rate`, `idle_rate`

**Override hooks** (both optional, base is no-op):
```python
def _record_unit_cycle(self, **kwargs) -> None:
    # Update unit-specific counters; all record_cycle() kwargs forwarded here

def _extra_summary(self) -> dict[str, Any]:
    # Return unit-specific derived stats merged into finalize() output
```

**Typical subclass:**
```python
class MyUnitPerfCount(PerfCounterBase):
    def __init__(self, name: str):
        super().__init__(name)
        self.cache_miss_cycles: int = 0

    def _record_unit_cycle(self, *, cache_miss: bool = False, **kwargs) -> None:
        if cache_miss:
            self.cache_miss_cycles += 1

    def _extra_summary(self) -> dict:
        return {
            "cache_miss_cycles": self.cache_miss_cycles,
            "cache_miss_rate": self._safe_div(self.cache_miss_cycles, self.total_cycles),
        }
```

**Call site in `tick()`:**
```python
self.perf_count.record_cycle(is_stalled=stalled, is_busy=busy, cache_miss=miss)
```

---

### `PerfConfig` — `perf_config.py`

Top-level configuration dataclass. One instance drives the entire framework.

```python
@dataclass
class PerfConfig:
    enabled_units: Set[str]                    # empty = all units enabled
    trace_range: Tuple[int, int] = (0, 0)      # (start, end) inclusive; (0,0) = off
    buffer_limit: int = 100_000
    flight_recorder: Optional[FlightRecorderConfig] = None
```

**Convenience constructors:**
```python
PerfConfig.disabled()                          # no telemetry at all
PerfConfig.summary_only(enabled_units=...)     # counters only, no traces
PerfConfig.full_trace(start, end, ...)         # counters + cycle-level traces
```

---

### `FlightRecorderConfig` — `perf_config.py`

Container for one or more `TriggerConfig` instances.

```python
@dataclass
class FlightRecorderConfig:
    triggers: List[TriggerConfig] = field(default_factory=list)

    @property
    def max_pre_capture_depth(self) -> int:
        # Shared deque depth = max pre_capture_depth across all triggers
```

---

### `TriggerConfig` — `perf_config.py`

A single named trigger condition for the flight recorder.

```python
@dataclass
class TriggerConfig:
    field: str                                           # kwargs key to watch
    operator: TriggerOperator = TriggerOperator.EQ       # comparison
    value: Any = True                                    # RHS of comparison
    watched_units: Set[str] = field(default_factory=set) # who can FIRE; empty=any
    capture_units: Set[str] = field(default_factory=set) # who gets CAPTURED; empty=all
    pre_capture_depth: int = 64                          # look-back buffer size
    post_capture_cycles: int = 32                        # cycles to capture after fire
    name: str = ""                                       # auto-generated if empty
    snapshot_providers: Set[str] = field(default_factory=set)
    snapshot_scopes: Dict[str, SnapshotScope] = field(default_factory=dict)
    snapshot_each_cycle: bool = False
```

- **`watched_units`** — which unit names can fire this trigger (independent of `capture_units`).
- **`capture_units`** — which unit trace rows are recorded in the capture window. These two sets are orthogonal.
- **`snapshot_providers`** — names of `Telemeter`-registered providers to invoke on fire.
- **`snapshot_scopes`** — per-provider `SnapshotScope`; provider name absent → full (unscoped) snapshot.
- **`snapshot_each_cycle`** — if True, providers are also called every cycle during the post-capture window (expensive; keep `post_capture_cycles` small).

**Multi-trigger semantics when triggers fire simultaneously:**
- The longest `post_capture_cycles` wins.
- `capture_units` are unioned; if any trigger has empty `capture_units` (all), the result is all.
- Snapshot scopes are **unioned per provider** — the broader scope wins (see `SnapshotScope.union()`).

---

### `TriggerOperator` — `perf_config.py`

```python
class TriggerOperator(Enum):
    EQ   # field == value
    NE   # field != value
    GT   # field >  value
    GTE  # field >= value
    LT   # field <  value
    LTE  # field <= value
```

---

### `SnapshotScope` — `perf_config.py`

Restricts a snapshot provider to a subset of warps and/or threads.

```python
@dataclass
class SnapshotScope:
    warps: Set[int] = field(default_factory=set)             # empty = all warps
    threads: Set[int] = field(default_factory=set)           # empty = all threads
    addresses: Set[int] = field(default_factory=set)         # empty = all addresses
    icache_addresses: Set[int] = field(default_factory=set)  # empty = all I-cache lines
    dcache_addresses: Set[int] = field(default_factory=set)  # empty = all D-cache lines

    def all_warps(self) -> bool: ...
    def all_threads(self) -> bool: ...
    def all_addresses(self) -> bool: ...
    def all_icache_addresses(self) -> bool: ...
    def all_dcache_addresses(self) -> bool: ...
    def hex_addresses(self) -> Set[str]: ...          # {'0x00001000', ...}
    def hex_icache_addresses(self) -> Set[str]: ...   # I-cache line addrs as hex strings
    def hex_dcache_addresses(self) -> Set[str]: ...   # D-cache line addrs as hex strings
    def union(self, other: SnapshotScope) -> SnapshotScope: ...
```

Addresses are plain Python `int` values — use hex literals for readability:
```python
SnapshotScope(addresses={0x1000, 0x1004, 0x2000})          # memory only
SnapshotScope(icache_addresses={0x0080, 0x0084})            # I-cache lines at those PCs
SnapshotScope(dcache_addresses={0x4000, 0x4040})            # D-cache lines
SnapshotScope(warps={0}, threads={0}, addresses={0xFF00})   # RF + memory
```

**`union()` semantics:** empty (unbounded) always wins for all three dimensions.
- `{0,1}.union({2,3})` → `{0,1,2,3}`
- `{}.union({2,3})` → `{}` (unbounded wins)
- `{}.union({})` → `{}`

The provider callable receives the `SnapshotScope` and is responsible for applying the filter — the Telemeter does not inspect the returned dict keys.

---

### `Telemeter` — `telemeter.py`

Central telemetry provider. One instance per simulation run, passed explicitly to all units.

```python
telemeter = Telemeter(config=PerfConfig, output_dir="perf_out")
```

**Key methods:**

| Method | When to call |
|---|---|
| `register_unit(unit)` | Once per `PerfCounterBase` instance at init time |
| `register_snapshot_provider(name, fn)` | After sim objects (RF, memory) exist, before loop |
| `is_trace_active(cycle) -> bool` | Guard before `record_trace()` in hot path |
| `record_trace(cycle, unit_name, **fields)` | Inside `tick()`, guarded by `is_trace_active()` |
| `check_triggers(unit_name, cycle, **fields)` | After `record_trace()` in `tick()` |
| `advance_flight_recorder(cycle)` | Once per sim cycle at the top of the main loop |
| `flush_traces()` | Called automatically; call manually if needed |
| `finalize()` | Once after the simulation loop exits |

**Snapshot provider signature:**
```python
provider(scope: Optional[SnapshotScope]) -> Dict[str, Any]
```
`scope=None` → full snapshot. Example registration:
```python
telemeter.register_snapshot_provider(
    "register_file",
    lambda scope: reg_file.snapshot(scope=scope),
)
```

---

## **Wiring Pattern — Unit `tick()` Method**

```python
def tick(self, cycle: int, ...) -> None:
    # --- simulation logic ---
    stalled = ...
    busy = ...
    cache_miss = ...

    # 1. Summary counters (always; no-op when unit is disabled in config)
    self.perf_count.record_cycle(is_stalled=stalled, is_busy=busy, cache_miss=cache_miss)

    # 2. Cycle-level trace (guarded — avoids dict allocation on inactive cycles)
    if self.telemeter.is_trace_active(cycle):
        self.telemeter.record_trace(cycle, self.name,
            warp_id=warp_id,
            instruction=str(instr.opcode) if instr else None,
            is_stalled=stalled,
            cache_miss=cache_miss,
        )

    # 3. Flight recorder trigger evaluation
    self.telemeter.check_triggers(self.name, cycle,
        is_stalled=stalled,
        cache_miss=cache_miss,
    )
```

**Main simulation loop:**
```python
for cycle in range(total_cycles):
    telemeter.advance_flight_recorder(cycle)  # top of loop
    # ... execute all units ...

telemeter.finalize()  # after loop exits
```

---

## **Output Files**

| File | Contents |
|---|---|
| `perf_out/traces.parquet` | All cycle-level trace rows (combined from parts at finalize) |
| `perf_out/perf_summary.parquet` | One row per unit: all `PerfCounterBase` summary stats |
| `perf_out/traces_part_NNNN.parquet` | Intermediate flush files (deleted by `finalize()`) |
| `perf_out/trigger_summary.parquet` | One `row_type="config"` row per registered `TriggerConfig` + one `row_type="event"` row per runtime fire; written by `finalize()` when a flight recorder is configured |

Read all traces in one shot:
```python
pl.read_parquet("perf_out/traces.parquet")
# or during a run before finalize():
pl.read_parquet(sorted(Path("perf_out").glob("traces_part_*.parquet")))
```

---

## **Code Style Guidelines for Copilot**

* Subclass `PerfCounterBase` for every new pipeline unit; never inline counter logic.
* Wrap `record_trace()` calls with `if self.telemeter.is_trace_active(cycle):` to avoid dict allocation overhead in the hot path.
* Use **snake_case** for all Parquet column names (`warp_id`, `is_stalled`, `cache_miss_rate`).
* Never use `pandas`. All DataFrame operations use `polars`.
* Never read-back-and-rewrite an existing Parquet file. Always write new part files.
* Pass `Telemeter` explicitly to module constructors — never use a module-level or class-level global.
* `SnapshotScope` with all empty sets is equivalent to no scope (full capture) — prefer `None` over `SnapshotScope()` to signal "full snapshot" in provider signatures.

---
