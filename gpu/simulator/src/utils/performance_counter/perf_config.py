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
        flight_recorder = FlightRecorderConfig(pre_stall_depth=64, post_stall_cycles=32),
    )
    telemeter = Telemeter(config=config, output_dir="results/run_0")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Set, Tuple


@dataclass
class FlightRecorderConfig:
    """
    Configuration for the flight-recorder (triggered tracing) feature.

    When a stall trigger fires on any watched unit, the circular pre-stall
    buffer is committed to the main trace buffer together with the next
    post_stall_cycles cycles of activity.

    Attributes
    ----------
    pre_stall_depth   : Number of cycles to retain in the circular buffer
                        before a trigger event (the "look-back" window).
    post_stall_cycles : Number of cycles to continue capturing after a
                        trigger event (the "look-ahead" window).
    watched_units     : Restrict triggers to this set of unit names.
                        Empty set (default) means *any* unit can trigger.
    """
    pre_stall_depth: int = 64
    post_stall_cycles: int = 32
    watched_units: Set[str] = field(default_factory=set)


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
