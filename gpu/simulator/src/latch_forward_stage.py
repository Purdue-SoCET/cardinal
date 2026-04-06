
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from collections import deque
from typing import NamedTuple
from bitstring import Bits
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from collections import deque
from bitstring import Bits 
from enum import Enum
from pathlib import Path
import sys
parent = Path(__file__).resolve().parents[2]
sys.path.append(str(parent))
from gpu.common.custom_enums_multi import Op


@dataclass
class MemRequest:
    addr: int
    size: int
    uuid: int
    warp_id: int
    pc: int 
    data: int 
    rw_mode: str
    remaining: int = 0

@dataclass 
class PredRequest:
    rd_en: int
    rd_wrp_sel: int
    rd_pred_sel: int
    prf_neg: int
    remaining: int

# @dataclass
class DecodeType:
    halt: int = 0
    EOP: int = 1
    MOP: int = 2 # the set default value
    EOS: int = 3
    empty: int = 4 # start up junk value..

###TEST CODE BELOW###
@dataclass
class ICacheEntry:
    tag: int
    data: Bits
    valid: bool = True
    last_used: int = 0

@dataclass
class FetchRequest:
    pc: int
    warp_id: int
    uuid: Optional[int] = None
    
class WarpState(Enum):
    READY = "ready"
    BARRIER = "barrier"
    STALL = "stall"
    HALT = "halt"

@dataclass
class Warp:
    pc: int
    id: int
    state: WarpState = WarpState.HALT
    finished_packet: bool = False
    in_flight: int = 0

@dataclass
class WarpGroup:
    warps: List[Warp]
    group_id: int
    halt: int = 1
    last_issue_even: bool = False
    issue: bool = False 

    halt_mask_even: Bits = field(default_factory=lambda: Bits(uint=(1 << 32) - 1, length=32))
    halt_mask_odd: Bits = field(default_factory=lambda: Bits(uint=(1 << 32) - 1, length=32))

@dataclass
class Instruction:
    # ----- required (no defaults) -----
    # STRUCTURAL HAZARD WITH PRED REG FILE WRITE AND READ LATER ON
    # INSTRUCTION JUST CONTAINS THE OPCODE INFORMATION
    # discusss more later about this..
    pc: Optional[Bits] = None
    warp_id: Optional[int] = None
    warp_group_id: Optional[int] = None
    num_operands: Optional[int] = None

    # ----- fields populated by decode ----
    intended_FU: Optional[str] = None 
    rs1: Optional[Bits] = None
    rs2: Optional[Bits] = None
    rd: Optional[Bits]= None
    src_pred: Optional[Bits]= None
    dest_pred: Optional[Bits]= None
    predicate: Optional[Bits] = None
    active_mask: Optional[Bits] = None
    opcode: Optional[Op]= None
    imm: Optional[Bits]= None
    csr_value: Optional[Any] = None
    csr_param: Optional[Any] = None
    
    packet: Optional[Bits] = None
    issued_cycle: Optional[int] = None
    wb_cycle: Optional[int] = None
    target_bank: int = None 
    target_regfile: Optional[str] = None

    rdat1: list[Bits] = field(default_factory=list)
    rdat2: list[Bits] = field(default_factory=list)
    wdat: list[Bits] = field(default_factory=list)
    wdat_pred: list[Bits] = field(default_factory=list)


    # ----- optional / with defaults (must come after ALL non-defaults) -----
    # this is for instruction data memory responses, populated by the MemController
    stage_entry: Dict[str, int] = field(default_factory=dict)
    stage_exit:  Dict[str, int] = field(default_factory=dict)
    fu_entries:  List[Dict]     = field(default_factory=list)
    



    
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

@dataclass
class ForwardingIF:
    payload: Optional[Any] = None
    wait: bool = False
    name: str = field(default="BackwardIF", repr=False)

    def push(self, data: Any) -> None:
        self.payload = data
        self.wait = False
    
    def pop(self) -> Optional[Any]:
        data = self.payload
        self.payload = None
        return data
    
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

# helper function for dumping memory
def dump_bytes(mem, base, n=4):
    for i in range(n):
        addr = base + i
        print(f"{addr:#06x}: {mem.memory.get(addr, 0):#04x}")
