from typing import Any, List, Set
from simulator.warp import WarpGroup
import statistics

# performance counter
from simulator.utils.performance_counter import PerfCounterBase

class SchedulerPerfCount(PerfCounterBase):
    def __init__(self, name: str) -> None:
        super().__init__(name)

        # scheduler numbers
        self.range: List[int] = [] # range of pcs to see deviation
        self.std_dev: List[float] = [] # std dev between warps

    def _record_unit_cycle(self, *, WarpTable: List[WarpGroup], **kwargs: Any) -> None:
        pcs = [warp.pc for group in WarpTable for warp in group.warps]
        self.std_dev.append(statistics.pstdev(pcs))
        self.range.append(max(pcs) - min(pcs))

        # return super()._record_unit_cycle(**kwargs)