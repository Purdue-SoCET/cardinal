from __future__ import annotations

from typing import Any

from simulator.utils.performance_counter.perf_counter_base import PerfCounterBase


class PredicateRegFilePerfCount(PerfCounterBase):
    """Performance counter for the predicate register file.

    Occupancy is measured at (warp, pred_index) slot granularity.  A slot is
    "valid" (occupied) when it has been written — i.e. its thread mask differs
    from the all-True reset/uninitialized state.

    Occupancy is normalized: 0.0 = empty, 1.0 = every slot across every warp
    has been written.

    full_cycles tracks cycles where at least one warp's partition is completely
    full (all num_preds_per_warp slots written).  Ideally each warp would have
    its own full counter, but for simplicity a single counter fires on ANY warp
    being full.
    """

    def __init__(self, name: str, num_warps: int, num_preds_per_warp: int) -> None:
        """
        Parameters
        ----------
        num_warps         : number of warps in the SM
        num_preds_per_warp: predicate registers per warp (from config: num_preds)
        """
        super().__init__(name)
        self.num_warps: int = num_warps
        self.num_preds_per_warp: int = num_preds_per_warp
        # total slots = num_warps * num_preds_per_warp
        self.total_slots: int = num_warps * num_preds_per_warp

        self.full_cycles: int = 0
        # store normalized occupancy (float 0.0–1.0) per cycle
        self._occupancy_samples: list[float] = []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def compute_occupancy(self, pred_reg_file) -> tuple[int, bool]:
        """Return (occupied_slots, any_warp_full).

        occupied_slots : count of (warp, pred) entries whose mask is not
                         all-True (i.e. has been written at least once).
        any_warp_full  : True if at least one warp has all num_preds_per_warp
                         slots written.  A single counter for this condition is
                         a simplification — ideally each warp would be tracked
                         separately, but that adds per-warp counters out of
                         scope here.
        """
        occupied_slots = 0
        any_warp_full = False
        for warp_preds in pred_reg_file.reg_file:
            warp_occupied = 0
            for mask in warp_preds:
                if not all(mask):
                    warp_occupied += 1
            occupied_slots += warp_occupied
            if warp_occupied == self.num_preds_per_warp:
                any_warp_full = True
        return occupied_slots, any_warp_full

    def sample(self, pred_reg_file, **kwargs) -> None:
        """Compute occupancy from reg file and record the cycle."""
        occupied, any_warp_full = self.compute_occupancy(pred_reg_file)
        is_busy = occupied > 0
        self.record_cycle(
            is_stalled=False,
            is_busy=is_busy,
            occupied_slots=occupied,
            any_warp_full=any_warp_full,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # PerfCounterBase hooks
    # ------------------------------------------------------------------

    def _record_unit_cycle(self, *, occupied_slots: int = 0, any_warp_full: bool = False, **_kwargs) -> None:
        normalized = self._safe_div(occupied_slots, self.total_slots)
        self._occupancy_samples.append(normalized)
        if any_warp_full:
            self.full_cycles += 1

    def _extra_summary(self) -> dict[str, Any]:
        n = len(self._occupancy_samples)
        avg_occupancy = self._safe_div(sum(self._occupancy_samples), n)
        p99_occupancy = _percentile(self._occupancy_samples, 99) if n else 0.0

        return {
            "num_warps": self.num_warps,
            "num_preds_per_warp": self.num_preds_per_warp,
            "total_slots": self.total_slots,
            # full_cycles: any warp's partition fully written this cycle
            # (simplified from per-warp tracking — see class docstring)
            "full_cycles": self.full_cycles,
            "full_cycle_rate": self._safe_div(self.full_cycles, self.total_cycles),
            "avg_occupancy": avg_occupancy,   # normalized 0.0–1.0
            "p99_occupancy": p99_occupancy,   # normalized 0.0–1.0
        }

    def _reset_unit_counters(self) -> None:
        self.full_cycles = 0
        self._occupancy_samples = []


def _percentile(samples: list[float], p: int) -> float:
    """Compute the p-th percentile of samples without numpy."""
    if not samples:
        return 0.0
    sorted_s = sorted(samples)
    n = len(sorted_s)
    # nearest-rank method
    rank = max(1, int((p / 100.0) * n + 0.5)) - 1
    rank = min(rank, n - 1)
    return sorted_s[rank]
