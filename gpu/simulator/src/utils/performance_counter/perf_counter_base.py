"""
PerfCounterBase
---------------
Base class for all per-unit performance counters in the GPU simulator.

Inherit from this class and override the two extension hooks:
    - _record_unit_cycle(**kwargs)  – called every cycle with any unit-specific
                                      keyword signals; base fields are already
                                      updated before this is called.
    - _extra_summary()              – return a dict of any additional derived
                                      stats to merge into the finalize output.

Typical usage in a pipeline stage
----------------------------------
    class MyUnitPerfCount(PerfCounterBase):
        def __init__(self, name: str):
            super().__init__(name)
            self.cache_miss_cycles: int = 0

        def _record_unit_cycle(self, *, cache_miss: bool = False, **kwargs) -> None:
            if cache_miss:
                self.cache_miss_cycles += 1

        def _extra_summary(self) -> dict:
            return {"cache_miss_cycles": self.cache_miss_cycles,
                    "cache_miss_rate": self._safe_div(self.cache_miss_cycles,
                                                      self.total_cycles)}

Then, inside the unit's tick() method:
    self.perf_count.record_cycle(
        is_stalled   = <bool>,
        is_busy      = <bool>,
        cache_miss   = <bool>,   # unit-specific
    )
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import polars as pl


class PerfCounterBase(ABC):
    """
    Abstract base class for all pipeline-unit performance counters.

    Common accumulated counters (available to all subclasses)
    ---------------------------------------------------------
    total_cycles  : int  – every call to record_cycle() increments this.
    stall_cycles  : int  – cycles where the unit could not make forward progress
                           (back-pressure from the stage ahead).
    busy_cycles   : int  – cycles where a valid instruction was being processed.
    idle_cycles   : int  – cycles where the unit held no valid work (NOP / bubble).

    Derived statistics (computed in finalize())
    -------------------------------------------
    stall_rate        : float  – stall_cycles  / total_cycles
    utilization_rate  : float  – busy_cycles   / total_cycles
    idle_rate         : float  – idle_cycles   / total_cycles
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, name: str, enabled: bool = True) -> None:
        """
        Parameters
        ----------
        name    : Unique human-readable identifier for this unit
                  (used as the 'unit_name' column in Parquet output).
        enabled : When False, record_cycle() becomes a no-op. Set to False
                  for units that are not in the active PerfConfig so that
                  the hot-path cost is a single bool check.
        """
        self.unit_name: str = name
        self.enabled: bool = enabled

        # --- common accumulators ---
        self.total_cycles: int = 0
        self.stall_cycles: int = 0
        self.busy_cycles: int = 0
        self.idle_cycles: int = 0

        # --- derived stats (populated by finalize()) ---
        self.stall_rate: float = 0.0
        self.utilization_rate: float = 0.0
        self.idle_rate: float = 0.0

        self._finalized: bool = False

    # ------------------------------------------------------------------
    # Hot-path entry point
    # ------------------------------------------------------------------

    def record_cycle(
        self,
        *,
        is_stalled: bool,
        is_busy: bool,
        **kwargs: Any,
    ) -> None:
        """
        Record one simulation cycle.  Call this once per cycle at the end of
        the unit's tick() method.

        Parameters
        ----------
        is_stalled : True when the stage ahead is applying back-pressure and
                     this unit cannot push its result forward.
        is_busy    : True when a valid (non-bubble / non-NOP) instruction is
                     present in this unit this cycle.
        **kwargs   : Any additional unit-specific signals forwarded verbatim
                     to _record_unit_cycle().
        """
        if not self.enabled:
            return

        self._finalized = False

        self.total_cycles += 1

        if is_stalled:
            self.stall_cycles += 1

        if is_busy:
            self.busy_cycles += 1
        else:
            self.idle_cycles += 1

        self._record_unit_cycle(is_stalled=is_stalled, is_busy=is_busy, **kwargs)

    # ------------------------------------------------------------------
    # Extension hooks
    # ------------------------------------------------------------------

    def _record_unit_cycle(self, **kwargs: Any) -> None:
        """
        Override in subclasses to update unit-specific counters each cycle.

        All kwargs passed to record_cycle() (including is_stalled / is_busy)
        are forwarded here.  The base implementation is intentionally a no-op.
        """

    def _extra_summary(self) -> dict[str, Any]:
        """
        Override in subclasses to add unit-specific derived stats to the
        output of finalize().  Return a plain dict; keys must be snake_case
        and must not overlap with base-class keys.
        """
        return {}

    # ------------------------------------------------------------------
    # Finalization and export
    # ------------------------------------------------------------------

    def finalize(self) -> dict[str, Any]:
        """
        Compute all derived statistics and return the complete summary dict.
        Safe to call multiple times; re-computation is idempotent.

        Returns a flat dict suitable for Parquet export or metadata logging.
        """
        self.stall_rate = self._safe_div(self.stall_cycles, self.total_cycles)
        self.utilization_rate = self._safe_div(self.busy_cycles, self.total_cycles)
        self.idle_rate = self._safe_div(self.idle_cycles, self.total_cycles)

        base: dict[str, Any] = {
            "unit_name": self.unit_name,
            "total_cycles": self.total_cycles,
            "stall_cycles": self.stall_cycles,
            "busy_cycles": self.busy_cycles,
            "idle_cycles": self.idle_cycles,
            "stall_rate": self.stall_rate,
            "utilization_rate": self.utilization_rate,
            "idle_rate": self.idle_rate,
        }

        base.update(self._extra_summary())

        self._finalized = True
        return base

    def reset(self) -> None:
        """Reset all counters to zero (e.g. between kernel launches)."""
        self.total_cycles = 0
        self.stall_cycles = 0
        self.busy_cycles = 0
        self.idle_cycles = 0
        self.stall_rate = 0.0
        self.utilization_rate = 0.0
        self.idle_rate = 0.0
        self._finalized = False
        self._reset_unit_counters()

    def _reset_unit_counters(self) -> None:
        """Override in subclasses to reset unit-specific counters."""

    # ------------------------------------------------------------------
    # Parquet I/O (Polars)
    # ------------------------------------------------------------------

    def to_parquet(self, directory: str = ".") -> None:
        """
        Write a single-row summary Parquet file for this unit.

        If a file already exists at the target path it is overwritten
        (use to_combined_parquet for multi-unit append workflows).
        """
        summary = self.finalize()
        df = pl.from_dicts([summary])
        path = Path(directory) / f"{self.unit_name}_perf_summary.parquet"
        df.write_parquet(str(path))

    @staticmethod
    def to_combined_parquet(
        perf_counts: list[PerfCounterBase],
        path: str,
    ) -> None:
        """
        Finalize and combine multiple unit counters into a single Parquet file.

        Parameters
        ----------
        perf_counts : List of PerfCounterBase instances (any mix of subclasses).
        path        : Full output file path (e.g. "results/all_units.parquet").
        """
        rows = [pc.finalize() for pc in perf_counts]
        df = pl.from_dicts(rows)
        df.write_parquet(path)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_div(numerator: int | float, denominator: int | float) -> float:
        """Division that returns 0.0 instead of raising ZeroDivisionError."""
        return float(numerator) / float(denominator) if denominator else 0.0

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(name={self.unit_name!r}, "
            f"total_cycles={self.total_cycles}, "
            f"busy={self.busy_cycles}, stall={self.stall_cycles})"
        )
