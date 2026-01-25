
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
parent = Path(__file__).resolve().parent
sys.path.append(str(parent))
from custom_enums_multi import Op

'''FROM DCACHE'''
# --- Cache Configuration ---
NUM_BANKS = 2           # Number of banks
NUM_SETS_PER_BANK = 16  # Number of sets per bank
NUM_WAYS = 8            # Number of ways in each set
BLOCK_SIZE_WORDS = 32   # Number of words in each block
WORD_SIZE_BYTES = 4     # Size of each word in BYTE
CACHE_SIZE = 32768      # Cache size [Bytes]
UUID_SIZE = 8           # From [UUID_SIZE-1:0] in lockup_free_cache.sv

# Address bit lengths
BYTE_OFF_BIT_LEN = (WORD_SIZE_BYTES - 1).bit_length()     # 4 - 1 = 3 -> 2 bits representation
BLOCK_OFF_BIT_LEN = (BLOCK_SIZE_WORDS - 1).bit_length() # 32 - 1 = 31 -> 5 bits representation
BANK_ID_BIT_LEN = (NUM_BANKS - 1).bit_length()          # 2 - 1 = 1 -> 1 bit representation
SET_INDEX_BIT_LEN = (NUM_SETS_PER_BANK - 1).bit_length()  # 16 - 1 = 15 -> 4 bit representation

# Tag = 32 - (2 + 5 + 1 + 4) = 20 bits
TAG_BIT_LEN = 32 - (SET_INDEX_BIT_LEN + BANK_ID_BIT_LEN + BLOCK_OFF_BIT_LEN + BYTE_OFF_BIT_LEN)

# Other constants
MSHR_BUFFER_LEN = 16    # The number of latches inside each MSHR buffer/Number of miss requests that can fit in each buffer
RAM_LATENCY_CYCLES = 200    # Static latency for each RAM access
HIT_LATENCY = 2         # Parameterized cache hit latency

@dataclass
class Addr:
    """Parses a 32-bit address into cache components."""
    tag: int            # The tag of the request
    set_index: int      # The set that the request wants to access
    bank_id: int        # The bank that the request wants to access
    block_offset: int   # The block offset that the reqeust wants to access
    byte_offset: int    # The byte that the request want to access (should always be 00)
    full_addr: int
    block_addr_val: int     # The block address of the request

    def __init__(self, addr: int):
        self.full_addr = addr
        
        # Gets the byte offset (which byte within a word)
        addr_temp = addr
        self.byte_offset = addr_temp & ((1 << BYTE_OFF_BIT_LEN) - 1) # Gets the lowest BYTE_OFF_BIT_LEN bits
        addr_temp >>= BYTE_OFF_BIT_LEN  # Removes the lowest BYTE_OFF_BIT_LEN bits for further processing
        
        # Gets the block offset (which word within a cache line)
        self.block_offset = addr_temp & ((1 << BLOCK_OFF_BIT_LEN) - 1)  # Gets the lowest BLOCK_OFF_BIT_LEN bits
        addr_temp >>= BLOCK_OFF_BIT_LEN # Removes the lowest BLOCK_OFF_BIT_LEN bits
        
        # Gets the bank id (which bank to access into)
        self.bank_id = addr_temp & ((1 << BANK_ID_BIT_LEN) - 1) #
        addr_temp >>= BANK_ID_BIT_LEN
        
        # Gets the set index (which set to access within the bank)
        self.set_index = addr_temp & ((1 << SET_INDEX_BIT_LEN) - 1) #
        addr_temp >>= SET_INDEX_BIT_LEN
        
        # Gets the tag
        self.tag = addr_temp & ((1 << TAG_BIT_LEN) - 1)
        
        # Address of the start of the block (includes bank index, set index, and the tag, removes the byte and block offset)
        self.block_addr_val = self.full_addr >> (BYTE_OFF_BIT_LEN + BLOCK_OFF_BIT_LEN) 

@dataclass
class dCacheRequest:
    """Wraps a pipeline instruction for the cache."""
    addr_val: int       # The actual memory request
    rw_mode: str        # 'read' or 'write'
    size: str # 'word' 'half' 'btye'
    store_value: Optional[int] = None    # The values that want to be written to cache
    halt: bool = False
    

    def __post_init__(self):
        self.addr = Addr(self.addr_val) # Create an Addr object and assign it to self.addr

@dataclass
class dMemResponse: # D$ -> LDST
    type: str
    req: Optional['dCacheRequest'] = None
    address: Optional[int] = None
    replay: bool = False
    is_secondary: bool = False
    data: Optional[Any] = None
    miss: bool = False
    hit: bool = False
    stall: bool = False
    uuid: Optional[int] = None
    flushed: bool = False

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
class dCacheFrame:
    """Simulates one cache line (frame)."""
    valid: bool = False # If the data is valid
    dirty: bool = False # If the data is dirty
    tag: int = 0    # Tag of the data

    # This contains the BLOCK_SIZE_WORDS number of words per frame
    # The field function is to ensure that every CacheFrame object has separate block lists and that writing to one frame's block doesn't overwrite another one's block
    block: List[int] = field(default_factory=lambda: [0] * BLOCK_SIZE_WORDS) 

@dataclass
class MSHREntry:
    """Simulates an MSHR entry (mshr_reg)."""
    valid: bool = True
    uuid: int = 0
    block_addr_val: int = 0
    write_status: List[bool] = field(default_factory=lambda: [False] * BLOCK_SIZE_WORDS)    # If the missed request was write or not
    write_block: List[int] = field(default_factory=lambda: [0] * BLOCK_SIZE_WORDS)      # The data to be written
    original_request: dCacheRequest = None # CHECK THIS
    cycles_to_ready: int = 0    # Internal timer for each entry in the buffer


@dataclass
class DecodeType:
    halt: int = 0
    EOP: int = 1
    MOP: int = 2
    Barrier: int = 3

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
    
@dataclass
class MemRequest:
    addr: int
    size: int
    uuid: int
    warp_id: int
    pc: int 
    remaining: int = 0

@dataclass
class Warp:
    pc: int
    group_id: int
    can_issue: bool = True
    halt: bool = True

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

@dataclass
class Instruction:
    # ----- required (no defaults) -----
    iid: Optional[int] = None
    pc: Bits = None
    intended_FSU: Optional[str] =None  # <-- no default here
    warp: Optional[int] = None
    warpGroup: Optional[int] = None

    opcode: Op = None
    rs1: Bits = None
    rs2: Bits = None
    rd: Bits = None

    # ----- optional / with defaults (must come after ALL non-defaults) -----
    pred: list[Bits] = field(default_factory=list)   # list of 1-bit Bits
    rdat1: list[Bits] = field(default_factory=list)
    rdat2: list[Bits] = field(default_factory=list)
    wdat: list[Bits] = field(default_factory=list)

    type: Optional[Any] = None
    packet: Optional[Bits] = None
    issued_cycle: Optional[int] = None
    stage_entry: Dict[str, int] = field(default_factory=dict)
    stage_exit:  Dict[str, int] = field(default_factory=dict)
    fu_entries:  List[Dict]     = field(default_factory=list)
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

# helper function for dumping memory
def dump_bytes(mem, base, n=4):
    for i in range(n):
        addr = base + i
        print(f"{addr:#06x}: {mem.memory.get(addr, 0):#04x}")
