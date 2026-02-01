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
from gpu_sim.cyclesim.src.mem.base import *


# --- Cache Configuration ---
NUM_BANKS = 2           # Number of banks
NUM_SETS_PER_BANK = 16  # Number of sets per bank
NUM_WAYS = 8            # Number of ways in each set
BLOCK_SIZE_WORDS = 32   # Number of words in each block
WORD_SIZE_BYTES = 4     # Size of each word in BYTE
CACHE_SIZE = 32768      # Cache size [Bytes]
UUID_SIZE = 8           # From [UUID_SIZE-1:0]

# Address bit lengths
BYTE_OFF_BIT_LEN = (WORD_SIZE_BYTES - 1).bit_length()     # 4 - 1 = 3 -> 2 bits representation
BLOCK_OFF_BIT_LEN = (BLOCK_SIZE_WORDS - 1).bit_length() # 32 - 1 = 31 -> 5 bits representation
BANK_ID_BIT_LEN = (NUM_BANKS - 1).bit_length()          # 2 - 1 = 1 -> 1 bit representation
SET_INDEX_BIT_LEN = (NUM_SETS_PER_BANK - 1).bit_length()  # 16 - 1 = 15 -> 4 bit representation

# Tag = 32 - (2 + 5 + 1 + 4) = 20 bits
TAG_BIT_LEN = 32 - (SET_INDEX_BIT_LEN + BANK_ID_BIT_LEN + BLOCK_OFF_BIT_LEN + BYTE_OFF_BIT_LEN)

# Other constants
MSHR_BUFFER_LEN = 16    # The number of latches inside each MSHR buffer/Number of miss requests that can fit in each buffer
HIT_LATENCY = 2         # Parameterized cache hit latency


# --- Simulator Modules ---
class MSHRBuffer:
    """Simulates cache_mshr_buffer.sv."""
    def __init__(self, buffer_len=MSHR_BUFFER_LEN, bank_id: int = 0):
        self.buffer = deque()   # The buffer containing all the requests
        self.max_size = buffer_len  # The number of latches in the buffer
        self.bank_stall = False     # If the bank needs to be stalled if the MSHR buffer is full

        self.bank_id = bank_id  # which bank the MSHR buffer belongs to

        # Generating a range of unqiue UUID for each MSHR buffer in a bank
        local_uuid_bits = UUID_SIZE - BANK_ID_BIT_LEN
        self.uuid_base_offset = bank_id << local_uuid_bits
        self.local_uuid_max = (2**local_uuid_bits)  # Max value for the local counter, e.g., 2**7 = 128

        self.local_uuid_counter = 0 # The current UUID
        self.last_issued_uuid = 0   # The last issued UUID
    
    def cycle(self):
        """Ages the entry at the head of the queue."""
        for entry in self.buffer:
            if entry.cycles_to_ready > 0:
                entry.cycles_to_ready -= 1
                
        if self.buffer: # If the buffer is not empty
            head_entry = self.buffer[0]
            if head_entry.cycles_to_ready > 0:
                logging.debug(f"MSHR(B{self.bank_id}): Entry {head_entry.uuid} waiting at head, {head_entry.cycles_to_ready} cycles left.")
            else:
                # This log is helpful to show when an entry becomes ready
                logging.debug(f"MSHR(B{self.bank_id}): Entry {head_entry.uuid} is ready at head.")

    def is_full(self) -> bool:  # If all the latches contain a miss request
        return len(self.buffer) >= self.max_size

    def find_secondary_miss(self, block_addr: int) -> Optional[MSHREntry]:  # If the miss request already exists in the buffer, return the existing entry
        for entry in self.buffer:
            if entry.block_addr_val == block_addr:
                return entry
        return None
    
    def check_stall(self, bank_empty: bool) -> bool:    # Check if MSHR buffer is full AND bank is busy
        is_full = self.is_full()
        is_busy = not bank_empty # is_busy is True if bank is busy handling a miss request
        
        if is_full and is_busy:
             # Stall if the bank is busy AND the buffer is full.
             # If the bank was *free*, it would drain one, making space.
             self.bank_stall = True
             return True
        
        # In all other cases (buffer not full, or bank is free), we don't stall.
        self.bank_stall = False
        return False

    def add_miss(self, req: dCacheRequest) -> Tuple[int, bool]:    # Add a miss to the MSHR buffer
        secondary = self.find_secondary_miss(req.addr.block_addr_val)   # See if the current request is a secondary miss
        if secondary:   # If the entry for that address exists (secondary miss)
            # Handle secondary miss
            logging.debug(f"MSHR(B{req.addr.bank_id}): Secondary miss for block 0x{req.addr.block_addr_val:X}")
            if req.rw_mode == 'write':  # If the current request is write
                # Merge the changes of the secondary request
                secondary.write_status[req.addr.block_offset] = True    # Overwrite the write status to be true
                secondary.write_block[req.addr.block_offset] = req.store_value  # Overwrite the write block to the current store value
            return secondary.uuid, False    # Return the UUID for the existing entry, and False because it didn't add another entry to the buffer
        
        if self.is_full():  # If the MSHR buffer is full (should have been checked earlier)
            raise Exception("MSHR full, should have been checked by caller")

        # Generate UUID locally using offset ---
        # Increment local counter and wrap around (0-15)
        self.local_uuid_counter = (self.local_uuid_counter + 1) % self.local_uuid_max
        
        # Combine base offset and counter to create a globally unique UUID
        # e.g., Bank 0: 0 + 0..127 -> 0..127
        # e.g., Bank 1: 128 + 0..127 -> 128..255
        uuid = self.uuid_base_offset + self.local_uuid_counter
        
        self.last_issued_uuid = uuid    # The current UUID becomes the last assigned UUID
        
        write_status = [False] * BLOCK_SIZE_WORDS   # Make a temporary false write_status
        write_block = [0] * BLOCK_SIZE_WORDS    # Prepopulate the write block with all 0s
        if req.rw_mode == 'write':  # If the request is write
            write_status[req.addr.block_offset] = True  # Change the write status for that specfic block to be True
            write_block[req.addr.block_offset] = req.store_value    # Store the write value to that specific block

        entry = MSHREntry(
            valid=True, # The current entry is valid
            uuid=uuid,  # The UUID for the current request
            block_addr_val=req.addr.block_addr_val, # The block address
            write_status=write_status,  # The write status (write or read)
            write_block=write_block,    # The data to be written
            original_request=req,    # The original request
            cycles_to_ready = MSHR_BUFFER_LEN # <-- MODIFIED: Set the timer
        )
        self.buffer.append(entry)   # Append the current MSHR entry to the buffer
        logging.debug(f"MSHR(B{req.addr.bank_id}): New primary miss (UUID {uuid}) for block 0x{req.addr.block_addr_val:X}")
        return uuid, True   # Return the UUID and true because a new entry was added to the buffer

    def get_head(self) -> Optional[MSHREntry]:  # Get the oldest entry in the buffer if it exists
        """MODIFIED: Gets the head entry ONLY if its timer is 0."""
        if self.buffer and self.buffer[0].cycles_to_ready == 0:
            return self.buffer[0]
        return None # Not ready or buffer is empty
        
    def pop_head(self):     # Pop the oldest entry of the buffer if it exists
        if self.buffer:
            self.buffer.popleft()

    def is_empty(self) -> bool:     # Check if the buffer is empty
        return len(self.buffer) == 0

class CacheBank:
    def __init__(self, bank_id: int, num_sets: int, num_ways: int, mem_req_if: LatchIF):
        self.bank_id = bank_id  # bank id
        self.num_sets = num_sets    # Number of sets in a bank
        self.num_ways = num_ways    # Number of ways in each set
        self.mem_req_if = mem_req_if    # The memory request to memory

        self.sets: List[List[dCacheFrame]] = [
            [dCacheFrame() for _ in range(num_ways)] for _ in range(num_sets)    # Create a cache frame for every way in all the sets
        ]
        self.lru: List[List[int]] = [
            list(range(num_ways)) for _ in range(num_sets)  # Creates a list of integers for each set. The number to the left is the MRU and the number to the right is the LRU
        ]
        
        # FSM State
        self.state = 'START'    # The defautl state
        self.active_mshr: Optional[MSHREntry] = None    # Default is not active MSHR
        self.latched_victim: Optional[dCacheFrame] = None    # Default is not latched victim
        self.latched_victim_way = 0     # Default is way 0
        self.fill_buffer = dCacheFrame()     # Used to hold the data for a miss
        self.busy = False   # Default is that each bank is not busy
        
        # Defaulting Memory Interface States
        self.waiting_for_mem = False
        self.incoming_mem_data = None

        # Flush state
        self.flush_set_idx = 0
        self.flush_way_idx = 0
    
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

    def check_hit(self, addr: Addr, rw_mode: str, data: int, size: str = 'word', raw_addr: int = 0) -> Tuple[bool, int]:
        set_idx = addr.set_index    # The set index
        tag = addr.tag      # The tag
        
        for i in range(self.num_ways):  # Check through all the ways in the set
            frame = self.sets[set_idx][i]   # Get the frame for that way
            if frame.valid and frame.tag == tag:    # if the fram is valid and the tags match --> The request hit in the cache
                self._update_lru(set_idx, i)    # Update the lru to make the current way index to be the MRU
                load_data = frame.block[addr.block_offset]  # Load the data from that specific word
                
                if rw_mode == 'write':  # if it's a write request
                    old_word = frame.block[addr.block_offset]
                    new_word = old_word
                    byte_offset = raw_addr & 0x3 # Get the bottom 2 bits
                    
                    if size == 'word':
                        new_word = data
                    elif size == 'half':
                        # Shift data to correct position and Mask
                        shift = byte_offset * 8
                        mask = 0xFFFF << shift
                        # Clear old bits, OR in new bits
                        new_word = (old_word & ~mask) | ((data << shift) & mask)
                    elif size == 'byte':
                        shift = byte_offset * 8
                        mask = 0xFF << shift
                        new_word = (old_word & ~mask) | ((data << shift) & mask)

                    frame.block[addr.block_offset] = new_word
                    frame.dirty = True  # Mark the data as dirty
                
                return True, load_data  # Return True (hit), and the hit data
        
        return False, 0 # Return False (miss), and a 0

    def start_miss_service(self, mshr_entry: MSHREntry):
        """
        Latches the MSHR entry and transitions from START.
        """
        self.active_mshr = mshr_entry   # Latch the oldest and valid MSHR entry
        self.busy = True    # Mark the bank as busy and can't accept more miss requests
        
        set_idx = mshr_entry.original_request.addr.set_index    # Get the set indes for the victim/MSHR
        victim_way = self._get_lru_way(set_idx)     # Find out the LRU way (victim)
        self.latched_victim = self.sets[set_idx][victim_way]    # Latch the victim cache frame
        self.latched_victim_way = victim_way    # latch the victim way
        
        # Creating the pull buffer that will replace the victim
        self.fill_buffer = dCacheFrame(
            valid=True,
            dirty=any(mshr_entry.write_status), # Dirty if the request writes to any of the blocks
            tag=mshr_entry.original_request.addr.tag,
            block=[0] * BLOCK_SIZE_WORDS    # The data is initialized to 0 for now
        )
        
        # Transition FSM
        if self.latched_victim.valid and self.latched_victim.dirty:     # if the victim is valid and dirty
            self.state = 'VICTIM_EJECT'     # Need to write back the data
            logging.debug(f"Bank {self.bank_id}: Miss. Dirty victim. -> VICTIM_EJECT")
        else:
            self.state = 'BLOCK_PULL'   # Otherwise, get the data from the RAM for the oldest missed request
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
        # Default outputs (RAM ports are no longer used) --> Sent to the lockupFreeCacheStage
        outputs = {
            'uuid_ready': False, 'uuid_out': 0, 'busy': self.busy
        }
        
        next_state = self.state     # Default next state (needed for START state)
        
        if self.state == 'START':   # Current state: START
            self.busy = False   # If in the START state, the cache bank is not busy
        
        elif self.state == 'BLOCK_PULL':    # Current state: BLOCK_PULL 
            if not self.waiting_for_mem and self.incoming_mem_data is None:     # (The RAM is ready to accept a new request)
                if self.mem_req_if.ready_for_push():
                    block_addr = self.active_mshr.block_addr_val << (BLOCK_OFF_BIT_LEN + BYTE_OFF_BIT_LEN)  # Calculating the block address in BYTE
                    # The request that's being sent to RAM
                    request = {
                        "addr": block_addr,
                        "size": BLOCK_SIZE_WORDS * 4,
                        "uuid": self.active_mshr.uuid,
                        "warp": self.bank_id,    # IMPORTANT: warp field stores the bank id
                        "rw_mode": "read"
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
                raw_bytes = self.incoming_mem_data.tobytes()    # Convert the incoming data to bytes

                for i in range(BLOCK_SIZE_WORDS):
                    if (self.active_mshr.write_status[i]):
                        self.fill_buffer.block[i] = self.active_mshr.write_block[i]
                    else:
                        start = i * 4
                        end = start + 4
                        if (start < len(raw_bytes)):
                            word_bytes = raw_bytes[start:end]
                            self.fill_buffer.block[i] = int.from_bytes(word_bytes, byteorder='little')
                        # The else block would be executed if the chunk of data returned from memory is smaller than the block size
                        else:
                            self.fill_buffer.block[i] = 0
                
                self.incoming_mem_data = None
                next_state = 'FINISH'
            
        elif (self.state == 'VICTIM_EJECT'):
            # Can send a write request to Memory
            if not(self.waiting_for_mem) and self.incoming_mem_data is None:
                if (self.mem_req_if.ready_for_push()):
                    victim_tag = self.latched_victim.tag
                    victim_set = self.active_mshr.original_request.addr.set_index

                    addr = (victim_tag << (SET_INDEX_BIT_LEN + BANK_ID_BIT_LEN + BLOCK_OFF_BIT_LEN + BYTE_OFF_BIT_LEN)) | \
                           (victim_set << (BANK_ID_BIT_LEN + BLOCK_OFF_BIT_LEN + BYTE_OFF_BIT_LEN)) | \
                           (self.bank_id << (BLOCK_OFF_BIT_LEN + BYTE_OFF_BIT_LEN))
                    
                    req_payload = {
                        "addr": addr,
                        "size": BLOCK_SIZE_WORDS * 4,   # Size in bytes
                        "uuid": self.active_mshr.uuid,
                        "warp_id": self.bank_id,
                        "rw_mode": "write",
                        "data": self.latched_victim.block
                    }
                    self.mem_req_if.push(req_payload)
                    self.waiting_for_mem = True
                
                else:   # Memory is not ready for a request
                    pass

            elif not(self.waiting_for_mem) and (self.incoming_mem_data == "WRITE_DONE"):
                self.incoming_mem_data = None
                next_state = 'BLOCK_PULL'
        
        # Finished victinm eject and block pull
        elif self.state == 'FINISH':
            set_idx = self.active_mshr.original_request.addr.set_index  # Get the set
            self.sets[set_idx][self.latched_victim_way] = self.fill_buffer  
            self._update_lru(set_idx, self.latched_victim_way)

            outputs['uuid_ready'] = True
            outputs['uuid_out'] = self.active_mshr.uuid
            self.active_mshr = None
            self.fill_buffer = dCacheFrame()
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
                    
                    # 2. Reconstruct the full byte address
                    # Addr = [ Tag | Set | Bank | BlockOff | ByteOff ]
                    addr = (victim_tag << (SET_INDEX_BIT_LEN + BANK_ID_BIT_LEN + BLOCK_OFF_BIT_LEN + BYTE_OFF_BIT_LEN)) | \
                           (self.flush_set_idx << (BANK_ID_BIT_LEN + BLOCK_OFF_BIT_LEN + BYTE_OFF_BIT_LEN)) | \
                           (self.bank_id << (BLOCK_OFF_BIT_LEN + BYTE_OFF_BIT_LEN))
                    
                    # 3. Define the payload
                    req_payload = {
                        "addr": addr,
                        "size": BLOCK_SIZE_WORDS * 4,
                        "uuid": 0, # Dummy UUID for flush operations
                        "warp": self.bank_id, # Used for routing response back to this bank
                        "rw_mode": "write",
                        "data": victim_frame.block # The data to write back
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
            behind_latch: Optional[LatchIF], # LSU -> Cache
            forward_ifs_write: Optional[Dict[str, ForwardingIF]], # Cache -> LSU
            mem_req_if: LatchIF, # Cache -> Memory
            mem_resp_if: LatchIF # Memory -> Cache
        ):
        super().__init__(
            name = name,
            behind_latch = behind_latch,
            forward_ifs_write = forward_ifs_write or {}
        )
        self.mem_req_if = mem_req_if    # The interface used by the cache to send to the memory
        self.mem_resp_if = mem_resp_if # The interface used the memory to send data back to cache

        self.DCACHE_LSU_IF_NAME = "DCache_LSU_Resp" # Pick a name
        if self.behind_latch and (self.DCACHE_LSU_IF_NAME in self.forward_ifs_write):
            self.behind_latch.forward_if = self.forward_ifs_write[self.DCACHE_LSU_IF_NAME]
        
        # Instantiate banks and MSHRs
        # Create NUM_BANKS number of banks each with NUM_SETS_PER_BANK of sets and NUM_WAYS of ways
        self.banks = [
            CacheBank(i, NUM_SETS_PER_BANK, NUM_WAYS, mem_req_if) for i in range(NUM_BANKS)
        ]
        # Create a MSHR buffer for each bank, PASSING IN THE BANK ID
        self.mshrs = [
            MSHRBuffer(MSHR_BUFFER_LEN, i) for i in range(NUM_BANKS)
        ]
        
        # State for the pipeline instruction this stage is processing
        self.pending_request: Optional[dCacheRequest] = None   # The current request
        # Map of in-flight misses, keyed by UUID
        self.active_misses: Dict[int, dCacheRequest] = {}

        # NEW: Create a pipeline for hit latency.
        # An item takes HIT_LATENCY cycles to pass through.
        # It is initialized with HIT_LATENCY number of 'None's.
        self.hit_pipeline = deque([None] * HIT_LATENCY, maxlen=HIT_LATENCY)
        self.hit_pipeline_busy = False  # A flag to block new hits while one is in flight.
        self.hit_stall = False
        
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

    def compute(self, input_data: Optional[Dict]) -> None:
        self.cycle_count += 1   # Increment the cycle count by 1
        logging.info(f"--- Cache Cycle {self.cycle_count} ---")
        self.stall = False

        # --- 1. Check for memory responses
        if (self.mem_resp_if.valid):
            resp = self.mem_resp_if.pop()
            if (resp):
                target_bank_id = resp["warp"]
                data = resp["data"]

                if (target_bank_id is not None) and (target_bank_id >= 0 and target_bank_id < NUM_BANKS):
                    self.banks[target_bank_id].complete_mem_access(data)
        
        # --- 2. Process Hit Pipeline (Output Stage) ---
        # Pop the item that entered the pipeline HIT_LATENCY cycles ago
        completed_hit_info = self.hit_pipeline.popleft() 
        this_cycle_lookup_result = None # Default to pushing a bubble
        
        # --- 3. Advance all internal components (Miss Handling) ---
        # MOVED UP: This logic must run first to generate bank_busy_signals
        # This (miss logic) can run in parallel with the hit pipeline

        # Cycle all MSHR buffers (to decrement timers)
        for mshr in self.mshrs:
            mshr.cycle()
        
        # 3a. Cycle all cache banks (FSMs)
        bank_busy_signals = []  # A list of busy signal from each bank
        for i in range(NUM_BANKS):  # Iterating throguh all the banks
            bank = self.banks[i]
            
            # Cycle the bank (no longer pass ram_resp)
            bank_out = bank.cycle() # Run the cycle method on ith bank
            bank_busy_signals.append(bank_out['busy'])  # Append the busy signal to the bank_busy_signals list
            
            # 3b. Check for completed misses & update outputs
            if bank_out['uuid_ready']:  # If the bank has finished serving a miss request
                uuid = bank_out['uuid_out'] # Get the UUID for the finished miss request
                if uuid in self.active_misses:  # if UUID is in the active misses list
                    req = self.active_misses.pop(uuid)    # Pop the UUID from the active miss dictionary
                    logging.info(f"Cache: Miss for UUID {uuid} (addr 0x{req.addr_val:X}) is complete.")
                    self.mshrs[i].pop_head()    # Pop the oldest entry from the MSHR buffer of the ith bank
                    
                    self.output_buffer.append(dMemResponse(
                        type = 'MISS_COMPLETE',
                        uuid = uuid,
                        req = req,
                        address = req.addr_val,
                        replay = True
                        ))
                
        # 3c. Service new misses if banks are ready
        for i in range(NUM_BANKS):  # Iterating through all banks again
            bank = self.banks[i]    # Get the ith bank
            mshr = self.mshrs[i]    # Get the ith MSHR buffer
            if bank.state == 'START' and not mshr.is_empty():   # If the bank state is START and the MSHR is not empty
                mshr_head = mshr.get_head() # Get the oldest MSHR request
                if mshr_head: # <-- MODIFIED: Check if get_head() returned a ready entry
                    logging.info(f"Cache: Bank {i} is starting service for miss UUID {mshr_head.uuid}")
                    bank.start_miss_service(mshr_head)  # Start the miss service method on the bank
        
        # 3e. NEW: Generate the busy signals *after* new misses have started
        bank_busy_signals = [bank.busy for bank in self.banks]

        # --- NEW: Check for Flush/Halt Command from Input ---
        if input_data and input_data.get('halt'):
            print(f"Cache: Received HALT signal. Starting flush.")
            self.flushing = True
            self.stall = True # Stop accepting inputs immediately
            
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
            if self.flushing:
                all_halted = True
                for bank in self.banks:
                    if bank.state == 'START':
                        bank.start_flush()
                        all_halted = False
                    elif bank.state != 'HALT':
                        all_halted = False

                if all_halted:
                     logging.info("Cache: Flush Complete.")
                     self.output_buffer.append(dMemResponse(
                         type = 'FLUSH_COMPLETE',
                         flushed  = True
                     ))
                         
                     self.flushing = False

        # --- 4. Handle Hit Completion & New Inputs ---
        
        if completed_hit_info: # This is the final cycle of the hit. The cache is busy outputting.
            req = completed_hit_info['req']
            logging.info(f"Cache: HIT for addr 0x{req.addr_val:X}")
            self.hit_pipeline_busy = False # The hit is complete, so unlock the pipeline.
            self.hit_stall = False

            self.output_buffer.append(dMemResponse(
                type = 'HIT_COMPLETE',
                hit = True,
                req = req,
                address = req.addr_val,
                data = completed_hit_info['data']
            ))

            
        else:
            # --- Handle the pipeline interface (Input Stage) ---
            # This block ONLY runs if the output stage is NOT busy
            if self.pending_request is None and not self.flushing:    # if not handling any request
                if (input_data):  
                    logging.info(f"Cache: Received new request: {input_data}")
                    self.pending_request = dCacheRequest(
                        addr_val=input_data.get('addr_val', 0),
                        rw_mode=input_data.get('rw_mode', 'read'),
                        size = input_data.get('size', 'word'),  # Data size (word, half, byte)
                        store_value=input_data.get('store_value', 0),
                        halt = input_data.get('halt', False)
                    )
                else:   # If the cache doesn't receive a valid request
                    logging.debug("No request sent to dcache")

            if not self.hit_pipeline_busy: # If there's no in-flight hit requests
                if self.pending_request:    # If currently handling a request
                    req = self.pending_request  # The request
                    addr = req.addr # The address
                    bank_id = addr.bank_id  # The bank ID
                    bank = self.banks[bank_id]  # The specific bank
                    mshr = self.mshrs[bank_id]  # The mshr buffer for that bank
                    
                    self.mem_out_uuid = mshr.last_issued_uuid   # The default of mem_out_UUID is just last issued UUID
                    
                    hit, data = bank.check_hit(
                        addr, 
                        req.rw_mode, 
                        req.store_value, 
                        req.size,
                        req.addr_val
                    )  # Check if the reqeust is a hit or miss
                    
                    if hit:
                        # This is Cycle 1 of the hit
                        logging.info(f"Cache: HIT for addr 0x{req.addr_val:X}. Pipelining.")
                        formatted_data = self.calc_data_size(data, req.addr_val, req.size)

                        # Prepare to push the hit result into the pipeline
                        this_cycle_lookup_result = {'data': formatted_data, 'req': req}
                        
                        self.hit_pipeline_busy = True # Lock the pipeline, it's now busy.
                        
                        self.pending_request = None # Consume the request
                        self.hit_stall = True
                    else:
                        # This is a MISS
                        logging.info(f"Cache: MISS for addr 0x{req.addr_val:X}")
            
                        # This now works because bank_busy_signals was populated in Step 3
                        bank_empty = not bank_busy_signals[bank_id] 
                        
                        if mshr.check_stall(bank_empty):
                            logging.warning(f"Cache: MSHR FULL for bank {bank_id}. Stalling pipeline.")
                            self.stall = True
                        else:
                            # It was an accepted miss
                            uuid, is_new = mshr.add_miss(req) # No longer pass new_uuid
                            req.uuid = uuid
                            
                            if is_new: # Only track new primary misses
                                self.active_misses[uuid] = req

                            self.output_buffer.append(dMemResponse(
                                type = 'MISS_ACCEPTED',
                                miss = True,
                                uuid = uuid,
                                req = req,
                                address = req.addr_val,
                                is_secondary = not is_new
                            ))
                            
                            self.pending_request = None
            
            else: # else for 'if not self.hit_pipeline_busy'
                logging.debug(f"Cache: Input stage stalled, hit pipeline is busy.")
                self.stall = True
                # We can't accept a new request (hit or miss) because the
                # hit pipeline resource is occupied.
                if self.hit_stall:
                    # We have a request, but the hit pipeline is busy
                    self.output_buffer.append(dMemResponse(
                        type = 'HIT_STALL',
                        stall = True,
                        req = self.pending_request
                    ))
                    
        # If we are still holding a request at the end of the cycle, 
        # we MUST tell the LSU to stall for the next cycle.
        if self.pending_request is not None:
            self.stall = True

        # --- 5. Push this cycle's lookup result into the hit pipeline ---
        # This pushes either the hit info (Cycle 1) or None (a bubble)
        self.hit_pipeline.append(this_cycle_lookup_result)

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
