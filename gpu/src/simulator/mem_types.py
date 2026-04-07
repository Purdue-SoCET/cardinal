
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
from common.custom_enums_multi import Op

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
    size: str # 'word' 'half' 'byte'
    store_value: Optional[int] = None    # The values that want to be written to cache
    halt: bool = False
    
    def __repr__(self):
        # We manually format the address as hex using 0x{...:X}
        return (f"dCacheRequest(addr_val=0x{self.addr_val:X}, "
                f"rw_mode='{self.rw_mode}', size='{self.size}', "
                f"store_value={self.store_value}, halt={self.halt})")

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

    def __repr__(self):
        # Handle Address: Only format as Hex if it exists
        if self.address is not None:
            addr_str = f"0x{self.address:X}"
        else:
            addr_str = "None"

        # Handle Data: Clean up formatting
        data_str = str(self.data)
        if self.data is not None and isinstance(self.data, int):
             data_str = hex(self.data)

        return (f"dMemResponse(type='{self.type}', "
                f"req={self.req}, "
                f"address={addr_str}, "  # Uses the safe string variable
                f"uuid={self.uuid}, "
                f"miss={self.miss}, hit={self.hit}, stall={self.stall}, "
                f"flushed={self.flushed})")

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