#!/usr/bin/env python3
"""
Python simulator for Lockup-Free Cache.
"""

import sys
import os
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from collections import deque
from simulator.latch_forward_stage import *
from dataclasses import dataclass, field

# All local versions of these classes as now we are not usig global variables for config and MSHR management. This allows us to have multiple cache instances if needed, and keeps the state encapsulated within the cache class.
@dataclass
class DCacheAddr:
    tag: int
    set_index: int
    bank_id: int
    block_offset: int
    byte_offset: int
    full_addr: int
    block_addr_val: int

    @classmethod
    def from_int(cls, addr: int, cfg: Dict[str, Any]) -> "DCacheAddr":
        addr_temp = addr

        byte_offset = addr_temp & ((1 << cfg["byte_off_bit_len"]) - 1)
        addr_temp >>= cfg["byte_off_bit_len"]

        block_offset = addr_temp & ((1 << cfg["block_off_bit_len"]) - 1)
        addr_temp >>= cfg["block_off_bit_len"]

        bank_id = addr_temp & ((1 << cfg["bank_id_bit_len"]) - 1)
        addr_temp >>= cfg["bank_id_bit_len"]

        set_index = addr_temp & ((1 << cfg["set_index_bit_len"]) - 1)
        addr_temp >>= cfg["set_index_bit_len"]

        tag = addr_temp & ((1 << cfg["tag_bit_len"]) - 1)

        block_addr_val = addr >> (
            cfg["byte_off_bit_len"] + cfg["block_off_bit_len"]
        )

        return cls(
            tag=tag,
            set_index=set_index,
            bank_id=bank_id,
            block_offset=block_offset,
            byte_offset=byte_offset,
            full_addr=addr,
            block_addr_val=block_addr_val,
        )


@dataclass
class DCacheRequest:
    addr_val: int
    rw_mode: str
    size: str
    store_value: Optional[int] = None
    halt: bool = False
    addr: Optional[DCacheAddr] = None

    def bind_addr(self, cfg: Dict[str, Any]) -> None:
        self.addr = DCacheAddr.from_int(self.addr_val, cfg)


@dataclass
class DMemResponse:
    type: str
    req: Optional["DCacheRequest"] = None
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
class DCacheFrame:
    block_size_words: int
    valid: bool = False
    dirty: bool = False
    tag: int = 0
    block: List[int] = field(default_factory=list)

    def __post_init__(self):
        if not self.block:
            self.block = [0] * self.block_size_words


@dataclass
class MSHREntry:
    block_size_words: int
    valid: bool = True
    uuid: int = 0
    block_addr_val: int = 0
    write_status: List[bool] = field(default_factory=list)
    write_block: List[int] = field(default_factory=list)
    original_request: Optional[DCacheRequest] = None
    cycles_to_ready: int = 0

    def __post_init__(self):
        if not self.write_status:
            self.write_status = [False] * self.block_size_words
        if not self.write_block:
            self.write_block = [0] * self.block_size_words

def build_dcache_config(cache_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = dict(cache_config or {})

    cfg.setdefault("num_banks", 2)
    cfg.setdefault("num_sets_per_bank", 16)
    cfg.setdefault("num_ways", 8)
    cfg.setdefault("block_size_words", 32)
    cfg.setdefault("word_size_bytes", 4)
    cfg.setdefault("cache_size", 32768)
    cfg.setdefault("uuid_size", 8)
    cfg.setdefault("mshr_buffer_len", 16)
    cfg.setdefault("ram_latency_cycles", 200)
    cfg.setdefault("hit_latency", 2)

    cfg["byte_off_bit_len"] = (cfg["word_size_bytes"] - 1).bit_length()
    cfg["block_off_bit_len"] = (cfg["block_size_words"] - 1).bit_length()
    cfg["bank_id_bit_len"] = (cfg["num_banks"] - 1).bit_length()
    cfg["set_index_bit_len"] = (cfg["num_sets_per_bank"] - 1).bit_length()
    cfg["tag_bit_len"] = 32 - (
        cfg["set_index_bit_len"]
        + cfg["bank_id_bit_len"]
        + cfg["block_off_bit_len"]
        + cfg["byte_off_bit_len"]
    )

    return cfg


class MSHRBuffer:
    """Simulates cache_mshr_buffer.sv."""
    def __init__(self, cfg: Dict[str, Any], bank_id: int = 0):
        self.cfg = cfg
        self.buffer = deque()
        self.max_size = cfg["mshr_buffer_len"]
        self.bank_stall = False
        self.bank_id = bank_id

        local_uuid_bits = cfg["uuid_size"] - cfg["bank_id_bit_len"]
        self.uuid_base_offset = bank_id << local_uuid_bits
        self.local_uuid_max = 2 ** local_uuid_bits

        self.local_uuid_counter = 0
        self.last_issued_uuid = 0
    
    def cycle(self):
        for entry in self.buffer:
            if entry.cycles_to_ready > 0:
                entry.cycles_to_ready -= 1
                
        if self.buffer:
            head_entry = self.buffer[0]
            if head_entry.cycles_to_ready > 0:
                logging.debug(
                    f"MSHR(B{self.bank_id}): Entry {head_entry.uuid} waiting at head, "
                    f"{head_entry.cycles_to_ready} cycles left."
                )
            else:
                logging.debug(f"MSHR(B{self.bank_id}): Entry {head_entry.uuid} is ready at head.")

    def is_full(self) -> bool:
        return len(self.buffer) >= self.max_size

    def find_secondary_miss(self, block_addr: int) -> Optional[MSHREntry]:
        for entry in self.buffer:
            if entry.block_addr_val == block_addr:
                return entry
        return None
    
    def check_stall(self, bank_empty: bool) -> bool:
        is_full = self.is_full()
        is_busy = not bank_empty
        
        if is_full and is_busy:
            self.bank_stall = True
            return True
        
        self.bank_stall = False
        return False

    def add_miss(self, req: DCacheRequest) -> Tuple[int, bool]:
        secondary = self.find_secondary_miss(req.addr.block_addr_val)
        if secondary:
            logging.debug(
                f"MSHR(B{req.addr.bank_id}): Secondary miss for block "
                f"0x{req.addr.block_addr_val:X}"
            )
            if req.rw_mode == "write":
                secondary.write_status[req.addr.block_offset] = True
                secondary.write_block[req.addr.block_offset] = req.store_value
            return secondary.uuid, False
        
        if self.is_full():
            raise Exception("MSHR full, should have been checked by caller")

        self.local_uuid_counter = (self.local_uuid_counter + 1) % self.local_uuid_max
        uuid = self.uuid_base_offset + self.local_uuid_counter
        self.last_issued_uuid = uuid
        
        write_status = [False] * self.cfg["block_size_words"]
        write_block = [0] * self.cfg["block_size_words"]

        if req.rw_mode == "write":
            write_status[req.addr.block_offset] = True
            write_block[req.addr.block_offset] = req.store_value

        entry = MSHREntry(
            block_size_words=self.cfg["block_size_words"],
            valid=True,
            uuid=uuid,
            block_addr_val=req.addr.block_addr_val,
            original_request=req,
            cycles_to_ready=self.cfg["mshr_buffer_len"],
        )
        self.buffer.append(entry)

        logging.debug(
            f"MSHR(B{req.addr.bank_id}): New primary miss (UUID {uuid}) "
            f"for block 0x{req.addr.block_addr_val:X}"
        )
        return uuid, True
        
    def get_head(self) -> Optional[MSHREntry]:
        if self.buffer and self.buffer[0].cycles_to_ready == 0:
            return self.buffer[0]
        return None
        
    def pop_head(self):     # Pop the oldest entry of the buffer if it exists
        if self.buffer:
            self.buffer.popleft()

    def is_empty(self) -> bool:     # Check if the buffer is empty
        return len(self.buffer) == 0

class CacheBank:
    def __init__(self, cfg: Dict[str, Any], bank_id: int, mem_req_if: LatchIF):
        self.cfg = cfg
        self.bank_id = bank_id
        self.num_sets = cfg["num_sets_per_bank"]
        self.num_ways = cfg["num_ways"]
        self.mem_req_if = mem_req_if

        self.sets: List[List[DCacheFrame]] = [
            [DCacheFrame(block_size_words=self.cfg["block_size_words"]) for _ in range(self.num_ways)]
            for _ in range(self.num_sets)
        ]
        self.lru: List[List[int]] = [
            list(range(self.num_ways))
            for _ in range(self.num_sets)
        ]
        
        self.state = "START"
        self.active_mshr: Optional[MSHREntry] = None
        self.latched_victim: Optional[DCacheFrame] = None
        self.latched_victim_way = 0
        self.fill_buffer = DCacheFrame(block_size_words=self.cfg["block_size_words"])
        self.busy = False
        
        # Defaulting Memory Interface States
        self.waiting_for_mem = False
        self.incoming_mem_data = None

        # Flush state
        self.flush_set_idx = 0
        self.flush_way_idx = 0

        self.hit_pipeline = deque(
            [None] * self.cfg["hit_latency"],
            maxlen=self.cfg["hit_latency"],
        )
        self.hit_pipeline_busy = False
    
    def start_flush(self):
        """Transitions the bank to FLUSH mode."""
        self.flush_set_idx = 0
        self.flush_way_idx = 0
        self.state = 'FLUSH'
        self.busy = True
        logging.debug(f"Bank {self.bank_id}: Starting FLUSH")

    def _update_lru(self, set_index: int, way: int):
        if way in self.lru[set_index]:
            self.lru[set_index].remove(way)     # Remove the way from the list first
        self.lru[set_index].insert(0, way)  # Insert the way at the 0th index to represent the MRU
        
    def _get_lru_way(self, set_index: int) -> int:
        return self.lru[set_index][-1]  # Get the LRU way (last of the list)

    def check_hit(
        self,
        addr: DCacheAddr,
        rw_mode: str,
        data: int,
        size: str = "word",
        raw_addr: int = 0,
    ) -> Tuple[bool, int]:
        set_idx = addr.set_index
        tag = addr.tag
        
        for i in range(self.num_ways):
            frame = self.sets[set_idx][i]
            if frame.valid and frame.tag == tag:
                self._update_lru(set_idx, i)
                load_data = frame.block[addr.block_offset]
                
                if rw_mode == "write":
                    old_word = frame.block[addr.block_offset]
                    new_word = old_word
                    byte_offset = raw_addr & 0x3
                    
                    if size == "word":
                        new_word = data
                    elif size == "half":
                        shift = byte_offset * 8
                        mask = 0xFFFF << shift
                        # Clear old bits, OR in new bits
                        new_word = (old_word & ~mask) | ((data << shift) & mask)
                    elif size == "byte":
                        shift = byte_offset * 8
                        mask = 0xFF << shift
                        new_word = (old_word & ~mask) | ((data << shift) & mask)

                    frame.block[addr.block_offset] = new_word
                    frame.dirty = True
                
                return True, load_data
        
        return False, 0

    def start_miss_service(self, mshr_entry: MSHREntry):
        self.active_mshr = mshr_entry
        self.busy = True
        
        set_idx = mshr_entry.original_request.addr.set_index
        victim_way = self._get_lru_way(set_idx)
        self.latched_victim = self.sets[set_idx][victim_way]
        self.latched_victim_way = victim_way
        
        self.fill_buffer = DCacheFrame(
            block_size_words=self.cfg["block_size_words"],
            valid=True,
            dirty=any(mshr_entry.write_status),
            tag=mshr_entry.original_request.addr.tag,
            block=[0] * BLOCK_SIZE_WORDS    # The data is initialized to 0 for now
        )
        
        if self.latched_victim.valid and self.latched_victim.dirty:
            self.state = "VICTIM_EJECT"
            logging.debug(f"Bank {self.bank_id}: Miss. Dirty victim. -> VICTIM_EJECT")
        else:
            self.state = "BLOCK_PULL"
            logging.debug(f"Bank {self.bank_id}: Miss. Clean victim. -> BLOCK_PULL")
        
        # 2. NOW, invalidate the line in the cache
        self.sets[set_idx][victim_way].valid = False
        return self.state

    def complete_mem_access(self, data):
        self.incoming_mem_data = data
        self.waiting_for_mem = False

    def cycle(self) -> Dict: # No longer takes ram_resp
        """
        Advances the cache bank FSM by one cycle.
        """
        completed_hit = self.hit_pipeline.popleft()
        self.hit_pipeline.append(None)

        if completed_hit:
            self.hit_pipeline_busy = False

        # Default outputs (RAM ports are no longer used) --> Sent to the lockupFreeCacheStage
        outputs = {
            'uuid_ready': False, 'uuid_out': 0, 'busy': self.busy,
            'completed_hit': completed_hit
        }
        
        next_state = self.state     # Default next state (needed for START state)
        
        if self.state == 'START':   # Current state: START
            self.busy = False   # If in the START state, the cache bank is not busy
        
        elif self.state == "BLOCK_PULL":
            if not self.waiting_for_mem and self.incoming_mem_data is None:
                if self.mem_req_if.ready_for_push():
                    block_addr = self.active_mshr.block_addr_val << (
                        self.cfg["block_off_bit_len"] + self.cfg["byte_off_bit_len"]
                    )

                    request = {
                        "addr": block_addr,
                        "size": self.cfg["block_size_words"] * self.cfg["word_size_bytes"],
                        "uuid": self.active_mshr.uuid,
                        "warp": self.bank_id,
                        "rw_mode": "read",
                        "src": "dcache",
                    }
                    self.mem_req_if.push(request)   # Push the request to memory
                    self.waiting_for_mem = True     # Wait for memory flag goes high
                    print(f"Bank {self.bank_id}: Sent READ req to Memory for 0x{block_addr:X}")
                else:
                    # Interface is busy, try again next cycle
                    pass
            
            # Data has arrived from the memory
            elif not self.waiting_for_mem and self.incoming_mem_data is not None:
                logging.debug(f"Bank {self.bank_id}: BLOCK_PULL complete.")
                raw_bytes = self.incoming_mem_data.tobytes()

                for i in range(self.cfg["block_size_words"]):
                    start = i * self.cfg["word_size_bytes"]
                    end = start + self.cfg["word_size_bytes"]

                    if start < len(raw_bytes):
                        word_bytes = raw_bytes[start:end]
                        ram_word = int.from_bytes(word_bytes, byteorder="little")
                    else:
                        ram_word = 0

                    if (self.active_mshr.write_status[i]):
                        req = self.active_mshr.original_request
                        data = self.active_mshr.write_block[i]
                        
                        size_masks = {'word': 0xFFFFFFFF, 'half': 0xFFFF, 'byte': 0xFF}
                        base_mask = size_masks.get(req.size, 0xFFFFFFFF)
                        
                        shift = (req.addr_val & 0x3) * 8
                        mask = base_mask << shift
                        
                        new_word = (ram_word & ~mask) | (data << shift)

                        self.fill_buffer.block[i] = new_word & 0xFFFFFFFF
                    else:
                        self.fill_buffer.block[i] = ram_word
                
                self.incoming_mem_data = None
                next_state = 'FINISH'
            
        elif (self.state == 'VICTIM_EJECT'):
            # Can send a write request to Memory
            if not(self.waiting_for_mem) and self.incoming_mem_data is None:
                if (self.mem_req_if.ready_for_push()):
                    victim_tag = self.latched_victim.tag
                    victim_set = self.active_mshr.original_request.addr.set_index

                    addr = (
                        victim_tag
                        << (
                            self.cfg["set_index_bit_len"]
                            + self.cfg["bank_id_bit_len"]
                            + self.cfg["block_off_bit_len"]
                            + self.cfg["byte_off_bit_len"]
                        )
                    ) | (
                        victim_set
                        << (
                            self.cfg["bank_id_bit_len"]
                            + self.cfg["block_off_bit_len"]
                            + self.cfg["byte_off_bit_len"]
                        )
                    ) | (
                        self.bank_id
                        << (
                            self.cfg["block_off_bit_len"]
                            + self.cfg["byte_off_bit_len"]
                        )
                    )
                    
                    req_payload = {
                        "addr": addr,
                        "size": self.cfg["block_size_words"] * self.cfg["word_size_bytes"],
                        "uuid": self.active_mshr.uuid,
                        "warp_id": self.bank_id,
                        "rw_mode": "write",
                        "data": self.latched_victim.block,
                        "src": "dcache",
                    }
                    self.mem_req_if.push(req_payload)
                    self.waiting_for_mem = True
                
                else:   # Memory is not ready for a request
                    pass

            elif not(self.waiting_for_mem) and (self.incoming_mem_data == "WRITE_DONE"):
                self.incoming_mem_data = None
                next_state = 'BLOCK_PULL'
        
        elif self.state == "FINISH":
            for i in range(self.cfg["block_size_words"]):
                if self.active_mshr.write_status[i]:
                    req = self.active_mshr.original_request
                    data = self.active_mshr.write_block[i]
                    
                    size_masks = {'word': 0xFFFFFFFF, 'half': 0xFFFF, 'byte': 0xFF}
                    base_mask = size_masks.get(req.size, 0xFFFFFFFF)
                    
                    shift = (req.addr_val & 0x3) * 8
                    mask = base_mask << shift
                    
                    # Merge it directly into the fill_buffer before committing
                    new_word = (self.fill_buffer.block[i] & ~mask) | (data << shift)
                    self.fill_buffer.block[i] = new_word & 0xFFFFFFFF

            set_idx = self.active_mshr.original_request.addr.set_index  # Get the set
            self.sets[set_idx][self.latched_victim_way] = self.fill_buffer  
            self._update_lru(set_idx, self.latched_victim_way)

            outputs['uuid_ready'] = True
            outputs['uuid_out'] = self.active_mshr.uuid
            self.active_mshr = None
            self.fill_buffer = DCacheFrame(block_size_words=self.cfg["block_size_words"])
            self.latched_victim = None
            self.busy = False
            next_state = 'START'
        
        elif self.state == 'FLUSH':
            # 1. Scan for dirty lines
            while self.flush_set_idx < self.num_sets:
                frame = self.sets[self.flush_set_idx][self.flush_way_idx]
                
                if frame.valid and frame.dirty:
                    # Found dirty line, pause scanning and go to WRITEBACK
                    next_state = 'WRITEBACK'
                    break 
                else:
                    # Clean or invalid, increment indices
                    self.flush_way_idx += 1
                    if self.flush_way_idx >= self.num_ways:
                        self.flush_way_idx = 0
                        self.flush_set_idx += 1
            
            # 2. If we scanned everything, go to HALT
            if self.flush_set_idx >= self.num_sets:
                next_state = 'HALT'
        
        elif self.state == 'WRITEBACK':
            # 1. Send write request to memory
            if not self.waiting_for_mem and self.incoming_mem_data is None:
                if self.mem_req_if.ready_for_push():
                    # 1. Get the tag from the specific line we are flushing
                    victim_frame = self.sets[self.flush_set_idx][self.flush_way_idx]
                    victim_tag = victim_frame.tag
                    
                    addr = (
                        victim_tag
                        << (
                            self.cfg["set_index_bit_len"]
                            + self.cfg["bank_id_bit_len"]
                            + self.cfg["block_off_bit_len"]
                            + self.cfg["byte_off_bit_len"]
                        )
                    ) | (
                        self.flush_set_idx
                        << (
                            self.cfg["bank_id_bit_len"]
                            + self.cfg["block_off_bit_len"]
                            + self.cfg["byte_off_bit_len"]
                        )
                    ) | (
                        self.bank_id
                        << (
                            self.cfg["block_off_bit_len"]
                            + self.cfg["byte_off_bit_len"]
                        )
                    )
                    
                    req_payload = {
                        "addr": addr,
                        "size": self.cfg["block_size_words"] * self.cfg["word_size_bytes"],
                        "uuid": 0,
                        "warp": self.bank_id,
                        "rw_mode": "write",
                        "data": victim_frame.block, # The data to write back,
                        "src": "dcache"
                    }
                    # --- END FIX ---

                    self.mem_req_if.push(req_payload)
                    self.waiting_for_mem = True
                    print(f"Bank {self.bank_id}: Flushing address 0x{addr:X}")
            
            # 2. Wait for Ack ("WRITE_DONE")
            elif not self.waiting_for_mem and (self.incoming_mem_data == "WRITE_DONE"):
                self.incoming_mem_data = None
                # Clear dirty bit so we don't flush it again
                self.sets[self.flush_set_idx][self.flush_way_idx].dirty = False
                # Advance iterator
                self.flush_way_idx += 1
                if self.flush_way_idx >= self.num_ways:
                    self.flush_way_idx = 0
                    self.flush_set_idx += 1
                # Go back to scanning
                next_state = 'FLUSH'
        
        elif self.state == 'HALT':
            # Stay here forever (until reset)
            self.busy = True
        
        self.state = next_state
        outputs['busy'] = self.busy
        return outputs

# --- Main Cache Stage ---

class LockupFreeCacheStage(Stage):
    """
    The main cache simulator
    """
    def __init__(
        self,
        name: str,
        behind_latch: Optional[LatchIF],
        forward_ifs_write: Optional[Dict[str, ForwardingIF]],
        mem_req_if: LatchIF,
        mem_resp_if: LatchIF,
        cache_config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            name=name,
            behind_latch=behind_latch,
            forward_ifs_write=forward_ifs_write or {},
        )

        self.cfg = build_dcache_config(cache_config)
        self.mem_req_if = mem_req_if
        self.mem_resp_if = mem_resp_if

        self.DCACHE_LSU_IF_NAME = "DCache_LSU_Resp" # Pick a name
        if self.behind_latch and (self.DCACHE_LSU_IF_NAME in self.forward_ifs_write):
            self.behind_latch.forward_if = self.forward_ifs_write[self.DCACHE_LSU_IF_NAME]
        
        # Instantiate banks and MSHRs
        # Create NUM_BANKS number of banks each with NUM_SETS_PER_BANK of sets and NUM_WAYS of ways
        self.banks = [
            CacheBank(self.cfg, i, mem_req_if)
            for i in range(self.cfg["num_banks"])
        ]
        # Create a MSHR buffer for each bank, PASSING IN THE BANK ID
        self.mshrs = [
            MSHRBuffer(self.cfg, i)
            for i in range(self.cfg["num_banks"])
        ]
        
        self.pending_request: Optional[DCacheRequest] = None
        self.active_misses: Dict[int, DCacheRequest] = {}
        
        self.cycle_count = 0
        self.output_buffer = deque()
        self.stall = False
        self.flushing = False
        # ---------------------------

    def calc_data_size (self, data: int, addr: int, size: str) -> int:
        """
        This helper function is used to calculate the data returned depending on the data size that was specificed in the dCacheRequest.
        It uses the byte offset (the last two bits of the instruction address) to know which byte to start counting from.
        """
        offset = addr & 0x3     # Extract the byte offset
        shift_amount = offset * 8   # The number of bits to be shifted to the right

        if (size == 'word'):
            return (data & 0xFFFF_FFFF)
        elif (size == 'half'):
            return ((data >> shift_amount) & 0xFFFF)
        elif (size == 'byte'):
            return ((data >> shift_amount) & 0xFF)

    def compute(self) -> None:
        self.cycle_count += 1   # Increment the cycle count by 1
        logging.info(f"--- Cache Cycle {self.cycle_count} ---")
        self.stall = False
        self.behind_latch.forward_if.set_wait(0)
        input_data = None

        # --- 1. Check for memory responses
        if (self.mem_resp_if.valid):
            resp = self.mem_resp_if.pop()
            print(f"Cache: Received memory response: {resp}")
            if (resp):
                target_bank_id = resp.warp_id
                if resp.packet:
                    data = resp.packet
                elif resp.status:
                    data = resp.status
                else:
                    data = None
                    
                if target_bank_id is not None and 0 <= target_bank_id < self.cfg["num_banks"]:
                    self.banks[target_bank_id].complete_mem_access(data)
        
        bank_busy_signals = []
        for i in range(self.cfg["num_banks"]):
            bank = self.banks[i]
            mshr = self.mshrs[i]
            mshr.cycle()
            
            bank_out = bank.cycle()
            bank_busy_signals.append(bank_out["busy"])
            
            if bank_out['completed_hit']:
                hit_info = bank_out['completed_hit']
                req = hit_info['req']

                self.output_buffer.append(
                    DMemResponse(
                        type="HIT_COMPLETE",
                        hit=True,
                        req=req,
                        address=req.addr_val,
                        data=hit_info["data"],
                    )
                )

            if bank_out["uuid_ready"]:
                uuid = bank_out["uuid_out"]
                if uuid in self.active_misses:
                    req = self.active_misses.pop(uuid)
                    logging.info(f"Cache: Miss for UUID {uuid} (addr 0x{req.addr_val:X}) is complete.")
                    self.mshrs[i].pop_head()    # Pop the oldest entry from the MSHR buffer of the ith bank
                    
                    self.output_buffer.append(
                    DMemResponse(
                            type="MISS_COMPLETE",
                            uuid=uuid,
                            req=req,
                            address=req.addr_val,
                            replay=True,
                        )
                    )
                
        for i in range(self.cfg["num_banks"]):
            bank = self.banks[i]
            mshr = self.mshrs[i]
            if bank.state == "START" and not mshr.is_empty():
                mshr_head = mshr.get_head()
                if mshr_head:
                    logging.info(f"Cache: Bank {i} is starting service for miss UUID {mshr_head.uuid}")
                    bank.start_miss_service(mshr_head)  # Start the miss service method on the bank
        
        # 3e. NEW: Generate the busy signals *after* new misses have started
        bank_busy_signals = [bank.busy for bank in self.banks]

        # Get Input if it exists
        if (self.behind_latch.valid) and (not self.stall):
            input_data = self.behind_latch.pop()

        # --- NEW: Check for Flush/Halt Command from Input ---
        if input_data and getattr(input_data, 'halt', False):
            print(f"Cache: Received HALT signal. Starting flush.")
            self.flushing = True
            self.stall = True # Stop accepting inputs immediately
            self.behind_latch.forward_if.set_wait(1)    # Set the wait signal high
            
        # --- NEW: Manage Flushing Process ---
        if self.flushing:
            all_halted = True
            for bank in self.banks:
                # If bank is idle, tell it to start flushing
                if bank.state == 'START':
                    bank.start_flush()
                    all_halted = False
                # If bank is doing normal work (BLOCK_PULL, etc) or Flushing, wait.
                elif bank.state != 'HALT':
                    all_halted = False
            
            # If every bank has reached HALT state
            if all_halted:
                print(f"Cache: Flush Complete.")

                response = DMemResponse(
                    type="FLUSH_COMPLETE",
                    flushed=True,
                    uuid=0,
                    address=0,
                    req=None,
                )
                 
                self.output_buffer.append(response)
                self.flushing = False # Stop checking
                for bank in self.banks:
                    bank.state = 'START' # Reset the state of each bank to START so they can accept new requests after flush

        # --- 4. Handle new inputs ---
        if self.pending_request is None and not self.flushing:    # if not handling any request
            if (input_data):  
                print(f"Cache: Received new request: {input_data}")
                self.pending_request = DCacheRequest(
                    addr_val=getattr(input_data, "addr_val", 0),
                    rw_mode=getattr(input_data, "rw_mode", "read"),
                    size=getattr(input_data, "size", "word"),
                    store_value=getattr(input_data, "store_value", 0),
                    halt=getattr(input_data, "halt", False),
                )

        if self.pending_request:    # If currently handling a request
            req = self.pending_request  # The request
            addr = req.addr # The address
            bank_id = addr.bank_id  # The bank ID
            target_bank = self.banks[bank_id]  # The specific bank
            mshr = self.mshrs[bank_id]  # The mshr buffer for that bank
            
            if not target_bank.hit_pipeline_busy:
                hit, data = target_bank.check_hit(
                    req.addr,
                    req.rw_mode,
                    req.store_value,
                    req.size,
                    req.addr_val,
                )
            
                if hit:
                    # This is Cycle 1 of the hit
                    logging.info(f"Cache: HIT for addr 0x{req.addr_val:X}. Pipelining.")
                    formatted_data = self.calc_data_size(data, req.addr_val, req.size)

                    target_bank.hit_pipeline[-1] = {'data': formatted_data, 'req': req}
                    target_bank.hit_pipeline_busy = True # Lock ONLY this bank

                    self.pending_request = None # Consume the request
                    self.hit_stall = False
                    self.behind_latch.forward_if.set_wait(0)
                else:
                    # This is a MISS
                    logging.info(f"Cache: MISS for addr 0x{req.addr_val:X}")

                    # This now works because bank_busy_signals was populated in Step 3
                    bank_empty = not bank_busy_signals[bank_id] 

                    if mshr.check_stall(bank_empty):
                        print(f"Cache: MSHR FULL for bank {bank_id}. Stalling pipeline.")
                        self.stall = True
                        self.behind_latch.forward_if.set_wait(1)
                    else:
                        # It was an accepted miss
                        uuid, is_new = mshr.add_miss(req) # No longer pass new_uuid
                        if is_new: # Only track new primary misses
                            self.active_misses[uuid] = req

                        self.output_buffer.append(
                            DMemResponse(
                                type="MISS_ACCEPTED",
                                miss=True,
                                uuid=uuid,
                                req=req,
                                address=req.addr_val,
                                is_secondary=not is_new,
                            )
                        )

                        self.pending_request = None
        
            else: # else for 'if not self.hit_pipeline_busy'
                logging.debug(f"Cache: Input stage stalled, hit pipeline is busy.")
                self.stall = True
                self.behind_latch.forward_if.set_wait(1)
                # We can't accept a new request (hit or miss) because the
                # hit pipeline resource is occupied.
                if self.pending_request is not None:
                    self.output_buffer.append(
                        DMemResponse(
                            type="HIT_STALL",
                            stall=True,
                            req=self.pending_request,
                        )
                    )
                    
        if self.pending_request is not None:
            self.stall = True
            self.behind_latch.forward_if.set_wait(1)

        # Pushing the top of the output buffer to the ahead latch (LSU)
        if self.DCACHE_LSU_IF_NAME in self.forward_ifs_write:
            interface = self.forward_ifs_write[self.DCACHE_LSU_IF_NAME]
            if not(interface.wait):
                if self.output_buffer:
                    event_to_send = self.output_buffer.popleft()
                    # Push to the named interface, not the dict
                    self.forward_ifs_write[self.DCACHE_LSU_IF_NAME].push(event_to_send)
                else:
                    self.forward_ifs_write[self.DCACHE_LSU_IF_NAME].push(None)
            else:
                # The LSU is busy, hold the data
                pass
