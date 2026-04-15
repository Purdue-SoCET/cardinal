"""
CachePerfCount
--------------
Performance counters for instruction cache (ICache) and data cache (DCache).

Both caches share this class — the unit_name field distinguishes them
in the Parquet output (e.g. "ICache_Stage", "dCache").

Tracked metrics
---------------
hit_count       : int  – cycles a request was served from the cache
miss_count      : int  – cycles a primary miss was accepted into MSHR / memory
eviction_count  : int  – cycles a dirty line was evicted (writeback initiated)

Derived statistics (computed in finalize())
-------------------------------------------
total_accesses  : int   – hit_count + miss_count
hit_rate        : float – hit_count  / total_accesses
miss_rate       : float – miss_count / total_accesses
"""

from __future__ import annotations

from typing import Any

from simulator.utils.performance_counter.perf_counter_base import PerfCounterBase


class CachePerfCount(PerfCounterBase):
    """Performance counters shared by ICache and DCache stages.

    Usage inside a cache stage's compute() method
    ----------------------------------------------
        # At the point where hit/miss is determined:
        self.perf_count.record_cycle(
            is_stalled   = <bool>,   # back-pressure from the stage ahead
            is_busy      = <bool>,   # a valid request is being processed
            is_hit       = <bool>,   # True if the request was a cache hit
            is_miss      = <bool>,   # True if a primary miss was accepted
            is_eviction  = <bool>,   # True if a dirty line was evicted
        )

    All boolean kwargs default to False so callers only pass what changed.
    """

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.hit_count: int = 0
        self.miss_count: int = 0
        self.eviction_count: int = 0

    # ------------------------------------------------------------------
    # Extension hooks
    # ------------------------------------------------------------------

    def _record_unit_cycle(
        self,
        *,
        is_hit: bool = False,
        is_miss: bool = False,
        is_eviction: bool = False,
        **kwargs: Any,
    ) -> None:
        if is_hit:
            self.hit_count += 1
        if is_miss:
            self.miss_count += 1
        if is_eviction:
            self.eviction_count += 1

    def _extra_summary(self) -> dict[str, Any]:
        total_accesses = self.hit_count + self.miss_count
        return {
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "eviction_count": self.eviction_count,
            "total_accesses": total_accesses,
            "hit_rate": self._safe_div(self.hit_count, total_accesses),
            "miss_rate": self._safe_div(self.miss_count, total_accesses),
        }

    def _reset_unit_counters(self) -> None:
        self.hit_count = 0
        self.miss_count = 0
        self.eviction_count = 0
