from enum import Enum
from dataclasses import dataclass, field
from typing import List
from bitstring import Bits

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
  