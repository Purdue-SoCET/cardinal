import sys, os

# Dynamically locate the project root (SoCET_GPU_FuncSim)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from gpu.gpu_sim.cyclesim.src.base_class import PipelineStage, SM, LoggerBase, PerfDomain, LatchInterface

from collections import deque
from dataclasses import dataclass, field
from typing import List, Any, Optional

@dataclass
class Warp:
    pc: int
    group_id: int
    can_issue: bool = True
    halt: bool = True

class SchedulerStage(PipelineStage):
    def __init__(self, parent_core, start_pc, warp_count: int = 32, warp_size: int = 32):
        super().__init__("Warp Scheduler", parent_core)

        # static shit
        self.warp_count: int = warp_count
        self.num_groups: int = (warp_count + 1) // 2
        self.warp_size: int = warp_size

        # warp table
        self.warp_table: List[Warp] = [Warp(pc=start_pc, group_id=wid // 2) for wid in range(warp_count)]

        # scheduler bookkeeping
        self.rr_index: int = 0
        self.max_issues_per_cycle: int = 1
        self.ready_queue = deque(range(warp_count))

        # debug
        self.issued_warp_last_cycle: Optional[int] = None

        # could add perf counters
    
    # PURE ROUND ROBIN RIGHT NOW, NEED TO FIND THE RR_INDEX
    def schedule(self):
        # arbitration

        # create instruction object with pc and warp ids/group ids
