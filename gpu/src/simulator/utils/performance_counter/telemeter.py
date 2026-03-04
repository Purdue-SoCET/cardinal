"""
Telemeter
---------
Central telemetry provider for the GPU simulator.

The Telemeter owns two distinct data streams:

1. **Summary counters** — every registered PerfCounterBase accumulates
   integer/float stats every cycle.  At simulation end, finalize() collects
   all units into a single summary Parquet file.

2. **Cycle-level traces** — arbitrary key/value rows emitted by units via
   record_trace().  Rows are buffered in a List[Dict] and flushed to Parquet
   when the buffer reaches PerfConfig.buffer_limit.

Flight Recorder (triggered tracing)
------------------------------------
When PerfConfig.flight_recorder is set, a collections.deque of depth
pre_stall_depth acts as a circular pre-trigger buffer.  Every call to
record_trace() appends to the deque instead of the main buffer while
tracing is in its normal (non-triggered) state.

Call trigger_flight_recorder(unit_name, cycle) when a stall is detected.
This commits the entire deque to the main buffer and puts the telemeter
into "post-trigger" mode, where it captures the next post_stall_cycles
cycles directly into the main buffer before returning to circular-buffer mode.

Typical wiring inside a tick() method
--------------------------------------
    # 1. Update the unit's own PerfCounterBase accumulators
    self.perf_count.record_cycle(is_stalled=stalled, is_busy=busy)

    # 2. Optionally emit a cycle-level trace row
    if self.telemeter.is_trace_active(cycle):
        self.telemeter.record_trace(cycle, self.name,
            warp_id=warp_id,
            instruction=str(instr.opcode) if instr else None,
            is_stalled=stalled,
        )

    # 3. Optionally trigger the flight recorder on stall
    if stalled:
        self.telemeter.trigger_flight_recorder(self.name, cycle)
"""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

import polars as pl

from simulator.utils.performance_counter.perf_config import PerfConfig
from simulator.utils.performance_counter.perf_counter_base import PerfCounterBase


class Telemeter:
    """
    Central telemetry provider.  One instance is created at simulation start
    and passed explicitly to every unit that participates in telemetry.

    Parameters
    ----------
    config     : PerfConfig instance controlling all telemetry behavior.
    output_dir : Directory where Parquet files are written.  Created if it
                 does not exist.
    """

    def __init__(self, config: PerfConfig, output_dir: str = "perf_out") -> None:
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Registered PerfCounterBase instances keyed by unit name
        self._units: Dict[str, PerfCounterBase] = {}

        # Cycle-level trace buffer
        self._trace_buffer: List[Dict[str, Any]] = []
        self._trace_file_index: int = 0   # incremented each flush (for multi-part files)

        # Flight recorder state
        self._fr_deque: Optional[deque] = None
        self._fr_post_cycles_remaining: int = 0
        self._fr_active: bool = False     # True while in post-trigger capture window

        if config.flight_recorder is not None:
            self._fr_deque = deque(maxlen=config.flight_recorder.pre_stall_depth)

    # ------------------------------------------------------------------
    # Unit registration
    # ------------------------------------------------------------------

    def register_unit(self, unit: PerfCounterBase) -> None:
        """
        Register a PerfCounterBase instance.

        The unit's enabled flag is set automatically based on PerfConfig,
        so modules can register unconditionally and let the config control
        whether work actually happens.
        """
        unit.enabled = self.config.is_unit_enabled(unit.unit_name)
        self._units[unit.unit_name] = unit

    def get_unit(self, unit_name: str) -> Optional[PerfCounterBase]:
        """Return the registered counter for a unit, or None."""
        return self._units.get(unit_name)

    # ------------------------------------------------------------------
    # Hot-path: trace active check
    # ------------------------------------------------------------------

    def is_trace_active(self, cycle: int) -> bool:
        """
        Fast range check — call this before record_trace() to avoid
        building the row dict when tracing is inactive.

            if self.telemeter.is_trace_active(cycle):
                self.telemeter.record_trace(...)
        """
        if not self.config.is_tracing_enabled():
            return False
        start, end = self.config.trace_range
        return start <= cycle <= end

    # ------------------------------------------------------------------
    # Cycle-level trace recording
    # ------------------------------------------------------------------

    def record_trace(self, cycle: int, unit_name: str, **fields: Any) -> None:
        """
        Emit one trace row.  Always call is_trace_active() first to avoid
        building the dict on inactive cycles.

        The row is appended to the flight-recorder deque (if configured and
        not currently in post-trigger capture mode) or directly to the main
        buffer.  Auto-flushes when the buffer reaches PerfConfig.buffer_limit.

        Parameters
        ----------
        cycle     : Current simulation cycle number.
        unit_name : Name of the emitting unit (used as a column value).
        **fields  : Arbitrary key/value pairs; keys become column names in
                    the output Parquet.  Use snake_case.
        """
        row: Dict[str, Any] = {"cycle": cycle, "unit_name": unit_name, **fields}

        if self._fr_deque is not None and not self._fr_active:
            # Pre-trigger: rotate through the circular buffer
            self._fr_deque.append(row)
        else:
            # Active tracing: straight to the main buffer
            self._trace_buffer.append(row)
            if len(self._trace_buffer) >= self.config.buffer_limit:
                self.flush_traces()

    # ------------------------------------------------------------------
    # Flight recorder
    # ------------------------------------------------------------------

    def trigger_flight_recorder(self, unit_name: str, cycle: int) -> None:
        """
        Fire the flight-recorder trigger from the named unit.

        If the unit is in PerfConfig.flight_recorder.watched_units (or that
        set is empty, meaning all units are watched), this commits the
        pre-trigger deque to the main buffer and enters post-trigger capture
        for `post_stall_cycles` cycles.

        Calling this while already in post-trigger mode resets the countdown
        (re-triggers), ensuring back-to-back stalls are fully captured.
        """
        fr_cfg = self.config.flight_recorder
        if fr_cfg is None:
            return

        # Check whether this unit is watched
        if fr_cfg.watched_units and unit_name not in fr_cfg.watched_units:
            return

        # Commit pre-trigger buffer to main buffer
        if self._fr_deque:
            self._trace_buffer.extend(self._fr_deque)
            self._fr_deque.clear()

        # Enter / reset post-trigger capture window
        self._fr_active = True
        self._fr_post_cycles_remaining = fr_cfg.post_stall_cycles

    def advance_flight_recorder(self) -> None:
        """
        Decrement the post-trigger cycle counter.  Call this once per
        simulation cycle (e.g. at the top of the main sim loop).

        When the counter reaches zero, the flight recorder returns to
        circular-buffer (pre-trigger) mode.
        """
        if self._fr_active and self._fr_post_cycles_remaining > 0:
            self._fr_post_cycles_remaining -= 1
            if self._fr_post_cycles_remaining == 0:
                self._fr_active = False

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    def flush_traces(self) -> None:
        """
        Flush the in-memory trace buffer to a new Parquet part file.

        Each flush produces an independent file:
            traces_part_0000.parquet
            traces_part_0001.parquet
            ...

        This avoids the read-back overhead of appending to an existing
        Parquet file (Parquet has no native append; the alternative is a
        full read → concat → rewrite which is O(total rows) per flush).

        At analysis time, read all parts in one shot:
            pl.read_parquet("perf_out/traces_*.parquet")
        or via DuckDB/Parquet Visualizer:
            SELECT * FROM read_parquet('perf_out/traces_*.parquet')
        """
        if not self._trace_buffer:
            return

        df = pl.from_dicts(self._trace_buffer)
        path = self.output_dir / f"traces_part_{self._trace_file_index:04d}.parquet"
        df.write_parquet(str(path))
        self._trace_buffer.clear()
        self._trace_file_index += 1

    def finalize(self) -> None:
        """
        End-of-simulation teardown:
          1. Flush any remaining trace rows.
          2. Combine all trace part files into a single traces.parquet.
          3. Finalize all registered unit counters.
          4. Write a combined summary Parquet.

        Call this exactly once after the simulation loop exits.
        """
        # Flush any remaining buffered rows
        self.flush_traces()

        # Combine all part files into one traces.parquet and delete the parts
        part_files = sorted(self.output_dir.glob("traces_part_*.parquet"))
        if part_files:
            df_traces = pl.read_parquet(
                [str(p) for p in part_files],
                allow_missing_columns=True,  # parts may have different column sets
            )
            df_traces.write_parquet(str(self.output_dir / "traces.parquet"))
            for part in part_files:
                part.unlink()

        if not self._units:
            return

        # Collect summaries from all registered units
        rows = [unit.finalize() for unit in self._units.values()]
        df = pl.from_dicts(rows)
        summary_path = self.output_dir / "perf_summary.parquet"
        df.write_parquet(str(summary_path))

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def registered_units(self) -> List[str]:
        """Names of all registered units."""
        return list(self._units.keys())

    @property
    def trace_buffer_size(self) -> int:
        """Number of rows currently in the in-memory trace buffer."""
        return len(self._trace_buffer)

    def __repr__(self) -> str:
        return (
            f"Telemeter(units={len(self._units)}, "
            f"buffered_rows={self.trace_buffer_size}, "
            f"output_dir={str(self.output_dir)!r})"
        )
