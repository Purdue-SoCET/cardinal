"""Unit test bench: This testbench sends a memory request to every bank in the cache. Initially the cache is empty and
every memory request misses. It fetches from main memory that has been prepopulated with 0x01010101 at every address.
Every missed request has a miss penalty of 200 cycles.
"""

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from collections import deque

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from custom_enums_multi import Op
from bitstring import Bits

@dataclass
class Instruction:
    pc: Bits
    intended_FSU: str 
    warp_id: int
    warp_group_id: int
    rs1: Bits
    rs2: Bits
    rd: Bits
    opcode: Op
    rdat1: list[Bits]
    rdat2: list[Bits]
    wdat: list[Bits]
    predicate: list[Bits] # list of Bits instances, each of length 1
    issued_cycle: Optional[int] = None
    stage_entry: Optional[Dict[str, int]] = field(default_factory=dict)   # stage -> first cycle seen
    stage_exit:  Optional[Dict[str, int]] = field(default_factory=dict)   # stage -> last cycle completed
    fu_entries:  Optional[List[Dict]]     = field(default_factory=list)   # [{fu:"ALU", enter: c, exit: c}, ...]
    wb_cycle: Optional[int] = None
    target_bank: int = None

    def mark_stage_enter(self, stage: str, cycle: int):
        self.stage_entry.setdefault(stage, cycle)

    def mark_stage_exit(self, stage: str, cycle: int):
        self.stage_exit[stage] = cycle

    def mark_fu_enter(self, fu: str, cycle: int):
        self.fu_entries.append({"fu": fu, "enter": cycle, "exit": None})

    def mark_fu_exit(self, fu: str, cycle: int):
        for e in reversed(self.fu_entries):
            if e["fu"] == fu and e["exit"] is None:
                e["exit"] = cycle
                return

    def mark_writeback(self, cycle: int):
        self.wb_cycle = cycle

### FIRST TWO SCHEMES ###

# @dataclass
# class ForwardingIF:
#     payload: Optional[Any] = None
#     wait: bool = False
#     name: str = field(default="BackwardIF", repr=False)

#     def push(self, data: Any) -> None:
#         self.payload = data
#         self.wait = False
    
#     def pop(self) -> Optional[Any]:
#         return self.payload
    
#     def set_wait(self, flag: bool) -> None:
#         self.wait = bool(flag)

#     def __repr__(self) -> str:
#         return (f"<{self.name} valid={self.valid} wait={self.wait} "
#             f"payload={self.payload!r}>")

# @dataclass
# class LatchIF:
#     payload: Optional[Any] = None
#     valid: bool = False
#     read: bool = False
#     name: str = field(default="LatchIF", repr=False)
#     forward_if: Optional[ForwardingIF] = None

#     def ready_for_push(self) -> bool:
#         if self.valid:
#             return False
#         if self.forward_if is not None and self.forward_if.wait:
#             return False
#         return True

#     def push(self, data: Any) -> bool:
#         if not self.ready_for_push():
#             return False
#         self.payload = data
#         self.valid = True
#         return True
    
#     def force_push(self, data: Any) -> None: # will most likely need a forceful push for squashing
#         self.payload = data
#         self.valid = True

#     def snoop(self) -> Optional[Any]: # may need this if we want to see the data without clearing the data
#         return self.payload if self.valid else None
    
#     def pop(self) -> Optional[Any]:
#         if not self.valid:
#             return None
#         data = self.payload
#         self.payload = None
#         self.valid = False
#         return data
    
#     def clear_all(self) -> None:
#         self.payload = None
#         self.valid = False
    
#     def __repr__(self) -> str: # idk if we need this or not
#         return (f"<{self.name} valid={self.valid} wait={self.wait} "
#                 f"payload={self.payload!r}>")
    
# @dataclass
# class Stage:
#     name: str
#     behind_latch: Optional[LatchIF] = None
#     ahead_latch: Optional[LatchIF] = None
#     forward_if_read: Optional[ForwardingIF] = None
#     forward_if_write: Optional[ForwardingIF] = None
    
#     def get_data(self) -> Any:
#         self.behind_latch.pop()

#     def send_output(self, data: Any) -> None:
#         self.ahead_latch.push(data)

#     def forward_signals(self, data: Any) -> None:
#         self.forward_if_write.push(data)

#     def compute(self, input_data: Any) -> Any:
#         # default computation, subclassess will override this
#         return input_data
    
### FORWARDING WITH DICTIONARIES ###

@dataclass
class ForwardingIF:
    payload: Optional[Any] = None
    wait: bool = False
    name: str = field(default="BackwardIF", repr=False)

    def push(self, data: Any) -> None:
        self.payload = data
        self.wait = False
    
    def pop(self) -> Optional[Any]:
        return self.payload
    
    def set_wait(self, flag: bool) -> None:
        self.wait = bool(flag)

    def __repr__(self) -> str:
        return (f"<{self.name} valid={self.valid} wait={self.wait} "
            f"payload={self.payload!r}>")

@dataclass
class LatchIF:
    payload: Optional[Any] = None
    valid: bool = False
    read: bool = False
    name: str = field(default="LatchIF", repr=False)
    forward_if: Optional[ForwardingIF] = None

    def ready_for_push(self) -> bool:
        if self.valid:
            return False
        if self.forward_if is not None and self.forward_if.wait:
            return False
        return True

    def push(self, data: Any) -> bool:
        if not self.ready_for_push():
            return False
        self.payload = data
        self.valid = True
        return True
    
    def force_push(self, data: Any) -> None: # will most likely need a forceful push for squashing
        self.payload = data
        self.valid = True

    def snoop(self) -> Optional[Any]: # may need this if we want to see the data without clearing the data
        return self.payload if self.valid else None
    
    def pop(self) -> Optional[Any]:
        if not self.valid:
            return None
        data = self.payload
        self.payload = None
        self.valid = False
        return data
    
    def clear_all(self) -> None:
        self.payload = None
        self.valid = False
    
    def __repr__(self) -> str: # idk if we need this or not
        return (f"<{self.name} valid={self.valid} wait={self.wait} "
                f"payload={self.payload!r}>")
    
@dataclass
class Stage:
    name: str
    behind_latch: Optional[LatchIF] = None
    ahead_latch: Optional[LatchIF] = None
    # forward_if_read: Optional[ForwardingIF] = None
    forward_ifs_read: Dict[str, ForwardingIF] = field(default_factory=dict)
    # forward_if_write: Optional[ForwardingIF] = None
    forward_ifs_write: Dict[str, ForwardingIF] = field(default_factory=dict)
    
    def get_data(self) -> Any:
        self.behind_latch.pop()

    def send_output(self, data: Any) -> None:
        self.ahead_latch.push(data)

    def forward_signals(self, forward_if: str, data: Any) -> None:
        self.forward_ifs_write[forward_if].push(data)

    def compute(self, input_data: Any) -> Any:
        # default computation, subclassess will override this
        return input_data
