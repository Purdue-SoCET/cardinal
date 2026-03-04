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
                    pre_capture_depth=64,
                    post_capture_cycles=32,
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
from typing import Any, List, Optional, Set, Tuple


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
