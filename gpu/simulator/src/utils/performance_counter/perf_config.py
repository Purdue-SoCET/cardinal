"""
PerfConfig
----------
Dataclass that drives all behavior of the telemetry system.
Pass one instance of this to the Telemeter at construction time.

Typical usage
-------------
    config = PerfConfig(
        enabled_units   = {"ALU_Int_0", "ALU_Float_0", "L1_Cache"},
        trace_range     = (1000, 5000),
        buffer_limit    = 100_000,
        flight_recorder = FlightRecorderConfig(
            triggers=[
                TriggerConfig(
                    field="is_stalled",
                    operator=TriggerOperator.EQ,
                    value=True,
                    watched_units={"ALU_Int_0", "ALU_Float_0"},
                    capture_units={"Decode_Stage", "ALU_Int_0", "ALU_Float_0"},
                    pre_capture_depth=64,
                    post_capture_cycles=32,
                    snapshot_providers={"register_file", "memory"},
                    snapshot_scopes={
                        "register_file": SnapshotScope(
                            warps={0, 1, 2, 3},   # only first 4 warps
                            threads={0},          # only thread 0 per warp
                        ),
                        # "memory" has no scope entry → full snapshot
                    },
                    snapshot_each_cycle=True,
                ),
                TriggerConfig(
                    field="cache_miss",
                    operator=TriggerOperator.EQ,
                    value=True,
                    watched_units={"L1_Cache"},
                    pre_capture_depth=16,
                    post_capture_cycles=8,
                ),
            ]
        ),
    )
    telemeter = Telemeter(config=config, output_dir="results/run_0")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class SnapshotScope:
    """
    Restricts a snapshot provider to a subset of warps, threads, and/or
    cache/memory addresses.

    Pass one instance per provider name in TriggerConfig.snapshot_scopes.
    The provider callable receives this scope and is responsible for
    applying it — the Telemeter does not parse the returned dict keys.

    All address fields accept plain Python int values; use hex literals
    (e.g. 0x1000) for readability.  An empty set always means "all" for
    that dimension.

    Attributes
    ----------
    warps            : Warp indices to include.  Empty = all warps.
    threads          : Thread indices within each warp.  Empty = all threads.
    addresses        : Data-memory addresses to include in a memory snapshot.
                       Empty = all addresses.
    icache_addresses : Instruction-cache line addresses (PCs) to include in
                       an I-cache snapshot.  Empty = all I-cache lines.
    dcache_addresses : Data-cache line addresses to include in a D-cache
                       snapshot.  Empty = all D-cache lines.

    Example
    -------
        # Register file — first 4 warps, thread 0 only
        SnapshotScope(warps={0, 1, 2, 3}, threads={0})

        # Data memory — specific addresses
        SnapshotScope(addresses={0x1000, 0x1004, 0x2000})

        # Instruction cache — specific PC addresses
        SnapshotScope(icache_addresses={0x0080, 0x0084})

        # Data cache — specific line addresses
        SnapshotScope(dcache_addresses={0x4000, 0x4040})

        # Combined — RF + both caches
        SnapshotScope(
            warps={0}, threads={0},
            icache_addresses={0x0080},
            dcache_addresses={0x4000},
        )

        SnapshotScope()  # everything (same as no scope)
    """
    warps: Set[int] = field(default_factory=set)
    threads: Set[int] = field(default_factory=set)
    addresses: Set[int] = field(default_factory=set)
    icache_addresses: Set[int] = field(default_factory=set)
    dcache_addresses: Set[int] = field(default_factory=set)

    def all_warps(self) -> bool:
        return not self.warps

    def all_threads(self) -> bool:
        return not self.threads

    def all_addresses(self) -> bool:
        return not self.addresses

    def all_icache_addresses(self) -> bool:
        return not self.icache_addresses

    def all_dcache_addresses(self) -> bool:
        return not self.dcache_addresses

    def hex_addresses(self) -> Set[str]:
        """Return data-memory addresses as zero-padded hex strings."""
        return {f"{addr:#010x}" for addr in self.addresses}

    def hex_icache_addresses(self) -> Set[str]:
        """Return I-cache addresses as zero-padded hex strings."""
        return {f"{addr:#010x}" for addr in self.icache_addresses}

    def hex_dcache_addresses(self) -> Set[str]:
        """Return D-cache addresses as zero-padded hex strings."""
        return {f"{addr:#010x}" for addr in self.dcache_addresses}

    def union(self, other: SnapshotScope) -> SnapshotScope:
        """
        Return the union of two scopes.

        An empty set in any dimension means "all" for that dimension;
        the result is also "all" (empty set) — the broader scope wins.

            {0,1} | {2,3}  -> {0,1,2,3}
            {}    | {2,3}  -> {}   (unbounded wins)
            {}    | {}     -> {}
        """
        def _merge(a: Set[int], b: Set[int]) -> Set[int]:
            return set() if (not a or not b) else a | b

        return SnapshotScope(
            warps=_merge(self.warps, other.warps),
            threads=_merge(self.threads, other.threads),
            addresses=_merge(self.addresses, other.addresses),
            icache_addresses=_merge(self.icache_addresses, other.icache_addresses),
            dcache_addresses=_merge(self.dcache_addresses, other.dcache_addresses),
        )

    def __repr__(self) -> str:
        parts = []
        if self.warps:            parts.append(f"warps={sorted(self.warps)}")
        if self.threads:          parts.append(f"threads={sorted(self.threads)}")
        if self.addresses:        parts.append(f"addrs={self.hex_addresses()}")
        if self.icache_addresses: parts.append(f"icache={self.hex_icache_addresses()}")
        if self.dcache_addresses: parts.append(f"dcache={self.hex_dcache_addresses()}")
        return f"SnapshotScope({', '.join(parts) or 'all'})"


class TriggerOperator(Enum):
    """Comparison operator used to evaluate a trigger condition."""
    EQ  = auto()   # field == value
    NE  = auto()   # field != value
    GT  = auto()   # field >  value
    GTE = auto()   # field >= value
    LT  = auto()   # field <  value
    LTE = auto()   # field <= value


@dataclass
class TriggerConfig:
    """
    A single named trigger condition for the flight recorder.

    When `field` in a record_trace() call satisfies `operator(value)` and
    the emitting unit is in `watched_units` (or watched_units is empty),
    the flight recorder fires: the pre-capture deque is committed and the
    next `post_capture_cycles` cycles are captured into the main buffer.

    Attributes
    ----------
    field              : The kwargs field name to watch (e.g. "is_stalled",
                         "cache_miss", "buffer_occupancy").
    operator           : TriggerOperator comparison to apply.
    value              : Right-hand side of the comparison.
    watched_units     : Restrict triggers to this set of unit names.
                        Empty set (default) means *any* unit can trigger.
    capture_units     : Units whose trace rows should be captured in the
                        pre and post windows when this trigger fires.
                        Empty set (default) means capture *all* units.
    pre_capture_depth  : Size of the circular look-back buffer for this
                         trigger.  Overrides FlightRecorderConfig default.
    post_capture_cycles: Cycles to capture after the trigger fires.
                         Overrides FlightRecorderConfig default.
    name               : Optional human-readable label (used in trace rows).
    """
    field: str
    operator: TriggerOperator = TriggerOperator.EQ
    value: Any = True
    watched_units: Set[str] = field(default_factory=set)
    capture_units: Set[str] = field(default_factory=set)
    pre_capture_depth: int = 64
    post_capture_cycles: int = 32
    name: str = ""
    snapshot_providers: Set[str] = field(default_factory=set)
    snapshot_scopes: Dict[str, SnapshotScope] = field(default_factory=dict)
    snapshot_each_cycle: bool = False
    """snapshot_providers  : Names of snapshot providers (registered on the
                            Telemeter via register_snapshot_provider()) to
                            invoke when this trigger fires.  An immediate
                            snapshot is always taken on fire.  If
                            snapshot_each_cycle is True, providers are also
                            called every cycle during the post-capture window.
    snapshot_scopes      : Optional per-provider SnapshotScope.  If a provider
                            name has no entry here its provider is called with
                            scope=None (full snapshot).  Use this to restrict
                            register-file snapshots to specific warps/threads.
    snapshot_each_cycle  : When True, call snapshot_providers every cycle
                           during the post-capture window, not just on fire.
                           Expensive — keep post_capture_cycles small.
    """

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"{self.field}_{self.operator.name}_{self.value}"

    def is_unit_watched(self, unit_name: str) -> bool:
        """Return True if this unit can fire the trigger."""
        return not self.watched_units or unit_name in self.watched_units

    def evaluate(self, field_value: Any) -> bool:
        """Evaluate the condition against a runtime field value."""
        match self.operator:
            case TriggerOperator.EQ:  return field_value == self.value
            case TriggerOperator.NE:  return field_value != self.value
            case TriggerOperator.GT:  return field_value >  self.value
            case TriggerOperator.GTE: return field_value >= self.value
            case TriggerOperator.LT:  return field_value <  self.value
            case TriggerOperator.LTE: return field_value <= self.value
        return False

    def matches(self, unit_name: str, fields: dict[str, Any]) -> bool:
        """
        Return True if this trigger should fire given the emitting unit
        and the kwargs dict from record_trace().
        """
        return (
            self.is_unit_watched(unit_name)
            and self.field in fields
            and self.evaluate(fields[self.field])
        )


@dataclass
class FlightRecorderConfig:
    """
    Container for one or more TriggerConfig instances.

    Any trigger firing commits the shared pre-capture deque and begins
    the post-capture window for that trigger's post_capture_cycles.
    If multiple triggers fire simultaneously, the longest post-capture
    window wins.

    The shared pre-capture deque depth is automatically set to the
    maximum pre_capture_depth across all triggers.

    Attributes
    ----------
    triggers : List of TriggerConfig instances to evaluate each cycle.
    """
    triggers: List[TriggerConfig] = field(default_factory=list)

    @property
    def max_pre_capture_depth(self) -> int:
        """Shared deque depth — max pre_capture_depth across all triggers."""
        return max((t.pre_capture_depth for t in self.triggers), default=64)


@dataclass
class PerfConfig:
    """
    Top-level configuration for the performance counter / tracing framework.

    Attributes
    ----------
    enabled_units       : Set of unit name strings that should have telemetry
                          active.  Units not in this set get a disabled
                          PerfCounterBase (record_cycle() becomes a no-op).
                          Pass an empty set to enable *all* registered units.
    trace_range         : (start_cycle, end_cycle) inclusive window for
                          cycle-level trace emission. Outside this window,
                          record_trace() is skipped entirely.
                          Use (0, 0) to disable cycle-level tracing while
                          still collecting summary counters.
    buffer_limit        : Number of trace rows to accumulate in memory before
                          flushing to Parquet.  Default 100,000.
    flight_recorder     : Optional flight-recorder configuration.  When None,
                          the flight-recorder feature is disabled.
    """
    enabled_units: Set[str] = field(default_factory=set)
    trace_range: Tuple[int, int] = (0, 0)
    buffer_limit: int = 100_000
    flight_recorder: Optional[FlightRecorderConfig] = None

    # ------------------------------------------------------------------
    # Convenience constructors
    # ------------------------------------------------------------------

    @classmethod
    def disabled(cls) -> PerfConfig:
        """All telemetry off — minimal hot-path cost."""
        return cls(enabled_units=set(), trace_range=(0, 0))

    @classmethod
    def summary_only(cls, enabled_units: Set[str] = None) -> PerfConfig:
        """
        Accumulate summary counters for the given units (or all if None)
        but do not emit any cycle-level trace rows.
        """
        return cls(
            enabled_units=enabled_units or set(),
            trace_range=(0, 0),
        )

    @classmethod
    def full_trace(
        cls,
        start: int,
        end: int,
        enabled_units: Set[str] = None,
        buffer_limit: int = 100_000,
        flight_recorder: FlightRecorderConfig = None,
    ) -> PerfConfig:
        """Collect both summary counters and cycle-level traces."""
        return cls(
            enabled_units=enabled_units or set(),
            trace_range=(start, end),
            buffer_limit=buffer_limit,
            flight_recorder=flight_recorder,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_unit_enabled(self, unit_name: str) -> bool:
        """
        Return True if telemetry should be active for the given unit.
        An empty enabled_units set means *all* units are enabled.
        """
        return not self.enabled_units or unit_name in self.enabled_units

    def is_tracing_enabled(self) -> bool:
        """Return True if cycle-level tracing is configured at all."""
        start, end = self.trace_range
        return end > start
