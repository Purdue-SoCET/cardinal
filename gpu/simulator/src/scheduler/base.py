import sys, os
from collections import deque
from dataclasses import dataclass, field
from typing import List, Any, Optional, Dict
from enum import Enum

@dataclass
class DecodeType:
    halt: int = 0
    EOP: int = 1
    MOP: int = 2
    Barrier: int = 3

@dataclass
class Instruction:
    iid: int
    pc: int
    issued_cycle: Optional[int] = None
    stage_entry: Dict[str, int] = field(default_factory=dict)   # stage -> first cycle seen
    stage_exit:  Dict[str, int] = field(default_factory=dict)   # stage -> last cycle completed
    fu_entries:  List[Dict]     = field(default_factory=list)   # [{fu:"ALU", enter: c, exit: c}, ...]
    wb_cycle: Optional[int] = None

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

class WarpState(Enum):
    READY = "ready"
    BARRIER = "barrier"
    STALL = "stall"
    HALT = "halt"

@dataclass
class WarpGroup:
    pc: int
    group_id: int
    last_issue_even: bool = False
    finished_packet: bool = False
    in_flight: int = 0
    state: WarpState = WarpState.READY

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
