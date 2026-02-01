from typing import NamedTuple
from bitstring import Bits
from simulator.latch_forward_stage import LatchIF, ForwardingIF
from typing import Optional

class dMemRequest(NamedTuple): # LDST -> D$
    addr: Bits
    write: bool # 1 for a write, 0 for a read
    pc: int

class dMemResponse(NamedTuple): # D$ -> LDST
    type: str
    hit: bool
    miss: bool
    uuid: int
    req: dMemRequest
    is_secondary: bool
    data: Optional[list[Bits]]
    addr: Bits
    pc: int
    

