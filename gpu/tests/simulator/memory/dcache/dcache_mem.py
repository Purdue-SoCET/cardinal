#!/usr/bin/env python3
import sys
import os
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from collections import deque
import math

# Adding path to the current directory to import files from another directory
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../../../../"))
if project_root not in sys.path:
    sys.path.append(project_root)

from gpu.simulator.src.mem.dcache import LockupFreeCacheStage
from gpu.simulator.base_class import *
from gpu.simulator.src.mem.Memory import Mem
from gpu.simulator.src.mem.mem_controller import MemController

BLOCK_SIZE_WORDS = 32       # 32 words per cache block

# Cache to memory interface
dCacheMemReqIF = LatchIF(name="dCacheMemReqIF")
memReqdCacheIF = LatchIF(name="memReqdCacheIF")

# LSU to Cache interface
LSU_dCache_IF = LatchIF(name="LSU_dCache_IF")
dCache_LSU_RESP_IF = ForwardingIF(name="DCache_LSU_Resp")

# iCache interfaces
ic_req = LatchIF("ICacheMemReqIF")
ic_resp = LatchIF("ICacheMemRespIF")

def make_test_pipeline():
    """
    This function connects creates the memory and dcache objects and connects the interfaces between them. It returns the objects and the interfaces (including the latches and "forwarding")
    """
    mem_backend = Mem(start_pc = 0x0000_0000,
                      input_file = "/home/shay/a/zhan4650/Desktop/gpu_seniorDesign/gpu/gpu/tests/simulator/memory/dcache/test.bin",
                      fmt = "bin")

    dCache = LockupFreeCacheStage(name = "dCache",
                                  behind_latch = LSU_dCache_IF,    # Change this to dummy
                                  forward_ifs_write = {"DCache_LSU_Resp": dCache_LSU_RESP_IF},   # Change this to dummy
                                  mem_req_if = dCacheMemReqIF,
                                  mem_resp_if = memReqdCacheIF
                                  )

    memStage = MemController(name = "Memory",
                             ic_req_latch = ic_req,
                             dc_req_latch = dCacheMemReqIF,
                             ic_serve_latch = ic_resp,
                             dc_serve_latch = memReqdCacheIF,
                             mem_backend = mem_backend,
                             latency = 5,
                             policy = "rr"
                            )
    
    for latch in [dCacheMemReqIF, memReqdCacheIF, LSU_dCache_IF, ic_req, ic_resp]:
        latch.clear_all()
    
    return {
        "dCache": dCache,
        "mem": memStage,
        "latches": {
            "dcache_mem": dCacheMemReqIF,
            "mem_dcache": memReqdCacheIF,
            "LSU_dCache": LSU_dCache_IF,
            "icache_mem_req": ic_req,
            "mem_icache_resp": ic_resp
        },
        "forward_if": LSU_dCache_IF.forward_if
    }

def print_latch_states(latches, cycle, before_after):
    """Prints the content of all latches with Hex formatting."""
    
    # --- Helper: Convert values to Hex Strings ---
    def to_hex(val):
        """Recursively converts integers to hex strings."""
        if isinstance(val, int):
            return f"0x{val:X}"
        elif isinstance(val, list):
            return [f"0x{v:X}" if isinstance(v, int) else v for v in val]
        return val

    def format_payload(payload):
        """Creates a readable Hex view of the payload."""
        if payload is None:
            return "None"

        # Case 1: Payload is a Dictionary (e.g., Input Requests)
        if isinstance(payload, dict):
            # Copy dict so we don't modify the actual simulation object
            p_view = payload.copy()
            # Convert specific keys to hex
            for key in ['addr_val', 'address', 'store_value', 'data', 'pc', 'addr']:
                if key in p_view and p_view[key] is not None:
                    p_view[key] = to_hex(p_view[key])
            return p_view

        # Case 2: Payload is an Object (e.g., dMemResponse)
        # We assume the object has a __repr__, but we can force it if needed
        return payload 
    # ---------------------------------------------

    if (before_after == "before"):
        print(f"=== Latch State Before Cycle {cycle} ===")
    else:
        print(f"=== Latch State at End of Cycle {cycle} ===")
    
    for name, latch in latches.items():
        payload = None

        # Extract payload based on latch type
        if hasattr(latch, 'valid') and latch.valid:
            payload = latch.payload
        elif hasattr(latch, 'payload') and latch.payload is not None:
            payload = latch.payload
            
        if payload is not None:
            # Print the formatted version
            print(f"  [{name}] VALID: {format_payload(payload)}")
        else:
            # Optional: Comment out to hide empty latches
            print(f"  [{name}] Empty")

def run_sim (start, cycles):
    for cycle in range(start, start+cycles):
        print(f"\n=== Cycle {cycle} ===")

        dcache_input = None
        cache_ready = (not dCache.stall)
        if cache_ready:
            if lsu_latch.valid:
                dcache_input = lsu_latch.pop()

        dCache.compute(input_data = dcache_input)
        mem.compute(input_data = None)
        response = resp_if.pop()
        if response:
            msg_type = response.type
            uuid = response.uuid
            data = response.data

            # --- Helper: Format Data as Hex ---
            data_hex = data
            if isinstance(data, int):
                data_hex = f"0x{data:08X}" # Format as 8-digit Hex
            elif isinstance(data, list):
                data_hex = [f"0x{x:X}" for x in data] # Format list items
            # ----------------------------------

            if (msg_type == 'MISS_ACCEPTED'):
                print(f"[Cycle {cycle}] LSU Received: MISS ACCEPTED (UUID: {uuid})")
            elif (msg_type == 'HIT_COMPLETE'):
                print(f"[Cycle {cycle}] LSU Received: HIT COMPLETE (Data: {data_hex})")
            elif (msg_type == 'MISS_COMPLETE'):
                print(f"[Cycle {cycle}] LSU Received: MISS COMPLETE (UUID: {uuid}) - Data is in cache")
            elif (msg_type == 'HIT_STALL'):
                print(f"[Cycle {cycle}] LSU Received: HIT STALL")
        
        if ic_resp.valid:
            i_response = ic_resp.pop()
            print(f"[Cycle {cycle}] ICache Received: Data from Memory (UUID: {i_response.get('uuid')})")
            print(f"Data: {i_response.get('data')}")

        print_latch_states(all_interfaces, cycle, "after")
    print(f"=== Test ended ===")
    return (cycles)

def print_banks():
    # --- 1. Calculate Bit Widths for Reconstruction ---
    # Offset: 32 words * 4 bytes = 128 bytes -> 7 bits (usually)
    offset_bits = int(math.log2(BLOCK_SIZE_WORDS * 4))
    
    # Bank Bits: log2(number of banks)
    num_banks = len(dCache.banks)
    bank_bits = int(math.log2(num_banks)) if num_banks > 1 else 0
    
    # Set Bits: log2(number of sets per bank)
    num_sets = len(dCache.banks[0].sets)
    set_bits = int(math.log2(num_sets))

    # Calculate Shift Amounts (Assuming Addr Structure: [ Tag | Set | Bank | Offset ])
    shift_bank = offset_bits
    shift_set = offset_bits + bank_bits
    shift_tag = offset_bits + bank_bits + set_bits
    # --------------------------------------------------

    for bank_id, bank in enumerate(dCache.banks):
        print(f"\n======== Bank {bank_id} ========")
        found_valid_line = False

        for set_id, cache_set in enumerate(bank.sets):
            set_has_valid_lines = any(frame.valid for frame in cache_set)

            if set_has_valid_lines:
                found_valid_line = True
                print(f"  ---- Set {set_id} ----")

                lru_list = bank.lru[set_id]
                print(f"    LRU Order: {lru_list} (Front=MRU, Back=LRU)")

                for way_id, frame in enumerate(cache_set):
                    if frame.valid:
                        tag_hex = f"0x{frame.tag:X}"
                        dirty_str = "D" if frame.dirty else " "
                        
                        # --- 2. Reconstruct the Address ---
                        # (Tag << shifts) | (Set << shifts) | (Bank << shifts)
                        full_addr = (frame.tag << shift_tag) | (set_id << shift_set) | (bank_id << shift_bank)
                        addr_hex = f"0x{full_addr:08X}" # Format as 8-digit Hex
                        # ----------------------------------

                        # Print Tag AND Address
                        print(f"    [Way {way_id}] V:1 {dirty_str} Tag: {tag_hex:<6} (Addr: {addr_hex})")

                        for i in range(0, BLOCK_SIZE_WORDS, 4):
                            w0 = f"0x{frame.block[i]:08X}"
                            w1 = f"0x{frame.block[i+1]:08X}"
                            w2 = f"0x{frame.block[i+2]:08X}"
                            w3 = f"0x{frame.block[i+3]:08X}"
                            print(f"        Block[{i:02d}:{i+3:02d}]: {w0} {w1} {w2} {w3}")

        if not found_valid_line:
            print(f"  (Bank is empty)")

if __name__ == "__main__":
    total_cycles = 0
    sim = make_test_pipeline()
    mem = sim["mem"]
    dCache = sim["dCache"]
    resp_if = sim["forward_if"]
    all_interfaces = sim["latches"]
    all_interfaces["DCache_LSU_Resp"] = sim["forward_if"]
    lsu_latch = sim["latches"]["LSU_dCache"]

    """
    1. TEST CASE R_B0_B1_s0 - Miss
    At the end of the of the test case, you can see the data stored in each bank. Compare this to memsim.hex to see if the data is correct.
    """
    with open("1.R_B0_B1_s0_MISS.txt", "w") as f:
        sys.stdout = f
        test_case = "R_B0_B1_s0 - Miss"
        print(f"Test Case: {test_case}")
        lsu_latch.push({"addr_val": 0x0000_0000, "rw_mode": "read", "size": "word"})    # Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0000_1080, "rw_mode": "read", "size": "word"})    # Bank1
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0000_2000, "rw_mode": "read", "size": "word"})    # Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0000_3080, "rw_mode": "read", "size": "word"})    # Bank1
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0000_4000, "rw_mode": "read", "size": "word"})    # 0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0000_5080, "rw_mode": "read", "size": "word"})    # 1
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0000_6000, "rw_mode": "read", "size": "word"})    # 0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0000_7080, "rw_mode": "read", "size": "word"})    # 1
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0000_8000, "rw_mode": "read", "size": "word"})    # 0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0000_9080, "rw_mode": "read", "size": "word"})    # 1
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0000_A000, "rw_mode": "read", "size": "word"})    # 0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0000_B080, "rw_mode": "read", "size": "word"})    # 1
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0000_C000, "rw_mode": "read", "size": "word"})    # 0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0000_D080, "rw_mode": "read", "size": "word"})    # 1
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0000_E000, "rw_mode": "read", "size": "word"})    # 0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0000_F080, "rw_mode": "read", "size": "word"})    # 1
        run_sim(total_cycles, 85)
        total_cycles += 85
        print_banks()


    """
    2. TEST CASE W_B0_B1_s1 - Miss
    At the end of the of the test case, you can see the data stored in each bank. Compare this to memsim.hex to see if the data is correct.
    """
    with open("2.W_B0_B1_s1_MISS.txt", "w") as f:
        sys.stdout = f
        test_case = "W_B0_B1_s1 - Miss"
        print(f"Test Case: {test_case}")
        lsu_latch.push({"addr_val": 0x0001_017C, "rw_mode": "write", "size": "word", "store_value": 0xAAAA_AAAA})    # Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0001_1184, "rw_mode": "write", "size": "word", "store_value": 0xAAAA_AAAA})    # Bank1
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0001_2100, "rw_mode": "write", "size": "word", "store_value": 0xAAAA_AAAA})    # Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0001_3180, "rw_mode": "write", "size": "word", "store_value": 0xAAAA_AAAA})    # Bank1
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0001_4100, "rw_mode": "write", "size": "word", "store_value": 0xAAAA_AAAA})    # Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0001_5180, "rw_mode": "write", "size": "word", "store_value": 0xAAAA_AAAA})    # Bank1
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0001_6100, "rw_mode": "write", "size": "word", "store_value": 0xAAAA_AAAA})    # Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0001_7180, "rw_mode": "write", "size": "word", "store_value": 0xAAAA_AAAA})    # Bank1
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0001_8100, "rw_mode": "write", "size": "word", "store_value": 0xAAAA_AAAA})    # Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0001_9180, "rw_mode": "write", "size": "word", "store_value": 0xAAAA_AAAA})    # Bank1
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0001_A100, "rw_mode": "write", "size": "word", "store_value": 0xAAAA_AAAA})    # Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0001_B180, "rw_mode": "write", "size": "word", "store_value": 0xAAAA_AAAA})    # Bank1
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0001_C100, "rw_mode": "write", "size": "word", "store_value": 0xAAAA_AAAA})    # Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0001_D180, "rw_mode": "write", "size": "word", "store_value": 0xAAAA_AAAA})    # Bank1
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0001_E100, "rw_mode": "write", "size": "word", "store_value": 0xAAAA_AAAA})    # Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0001_F180, "rw_mode": "write", "size": "word", "store_value": 0xAAAA_AAAA})    # Bank1
        run_sim(total_cycles, 85)
        total_cycles += 85
        print_banks()
    

    """
    3. TEST CASE R_B0_B1_s0 - Hit
    """
    with open("3.R_B0_B1_s0_HIT.txt", "w") as f:
        sys.stdout = f
        test_case = "R_B0_B1_s0 - Hit"
        print(f"Test Case: {test_case}")
        lsu_latch.push({"addr_val": 0x0000_0000, "rw_mode": "read", "size": "word"})    # Bank0
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0000_1080, "rw_mode": "read", "size": "word"})    # Bank1
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0000_2000, "rw_mode": "read", "size": "word"})    # Bank0
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0000_3080, "rw_mode": "read", "size": "word"})    # Bank1
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0000_4000, "rw_mode": "read", "size": "word"})    # 0
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0000_5080, "rw_mode": "read", "size": "word"})    # 1
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0000_6000, "rw_mode": "read", "size": "word"})    # 0
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0000_7080, "rw_mode": "read", "size": "word"})    # 1
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0000_8000, "rw_mode": "read", "size": "word"})    # 0
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0000_9080, "rw_mode": "read", "size": "word"})    # 1
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0000_A000, "rw_mode": "read", "size": "word"})    # 0
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0000_B080, "rw_mode": "read", "size": "word"})    # 1
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0000_C000, "rw_mode": "read", "size": "word"})    # 0
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0000_D080, "rw_mode": "read", "size": "word"})    # 1
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0000_E000, "rw_mode": "read", "size": "word"})    # 0
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0000_F080, "rw_mode": "read", "size": "word"})    # 1
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        print_banks()


    """
    4. TEST CASE W_B0_B1_s1 - Hit
    """
    with open("4.W_B0_B1_s1_HIT.txt", "w") as f:
        sys.stdout = f
        test_case = "W_B0_B1_s1 - Hit"
        print(f"Test Case: {test_case}")
        lsu_latch.push({"addr_val": 0x0001_017C, "rw_mode": "write", "size": "word", "store_value": 0xDEAD_BEEF})    # Bank0
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0001_1184, "rw_mode": "write", "size": "word", "store_value": 0xDEAD_BEEF})    # Bank1
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0001_2100, "rw_mode": "write", "size": "word", "store_value": 0xDEAD_BEEF})    # Bank0
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0001_3180, "rw_mode": "write", "size": "word", "store_value": 0xDEAD_BEEF})    # Bank1
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0001_4100, "rw_mode": "write", "size": "word", "store_value": 0xDEAD_BEEF})    # Bank0
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0001_5180, "rw_mode": "write", "size": "word", "store_value": 0xDEAD_BEEF})    # Bank1
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0001_6100, "rw_mode": "write", "size": "word", "store_value": 0xDEAD_BEEF})    # Bank0
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0001_7180, "rw_mode": "write", "size": "word", "store_value": 0xDEAD_BEEF})    # Bank1
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0001_8100, "rw_mode": "write", "size": "word", "store_value": 0xDEAD_BEEF})    # Bank0
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0001_9180, "rw_mode": "write", "size": "word", "store_value": 0xDEAD_BEEF})    # Bank1
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0001_A100, "rw_mode": "write", "size": "word", "store_value": 0xDEAD_BEEF})    # Bank0
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0001_B180, "rw_mode": "write", "size": "word", "store_value": 0xDEAD_BEEF})    # Bank1
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0001_C100, "rw_mode": "write", "size": "word", "store_value": 0xDEAD_BEEF})    # Bank0
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0001_D180, "rw_mode": "write", "size": "word", "store_value": 0xDEAD_BEEF})    # Bank1
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0001_E100, "rw_mode": "write", "size": "word", "store_value": 0xDEAD_BEEF})    # Bank0
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        lsu_latch.push({"addr_val": 0x0001_F180, "rw_mode": "write", "size": "word", "store_value": 0xDEAD_BEEF})    # Bank1
        run_sim(total_cycles, 1 + HIT_LATENCY)
        total_cycles += 1 + HIT_LATENCY
        print_banks()


    """
    5. TEST CASE Sec_Miss_B0_s2 - RAW
    The same UUID should be sent from the cache to the LSU to alert LSU that two missed requests have merged into one
    """
    with open("5.Sec_Miss_B0_s2_RAW.txt", "w") as f:
        sys.stdout = f
        test_case = "Sec_Miss_B0_s2 - RAW"
        print(f"Test Case: {test_case}")
        lsu_latch.push({"addr_val": 0x0002_0200, "rw_mode": "write", "size": "word", "store_value": 0xDEAD_BEEF})    # Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0002_0200, "rw_mode": "read", "size": "word"})
        run_sim(total_cycles, 24)
        total_cycles += 24
        print_banks()


    """
    6. TEST CASE Sec_Miss_B0_s4 - WAW
    The same UUID should be sent from the cache to the LSU to alert LSU that two missed requests have merged into one
    The LSU should assume that the latest data will be written
    """
    with open("6.Sec_Miss_B0_s4_WAW.txt", "w") as f:
        sys.stdout = f
        test_case = "Sec_Miss_B0_s4 - WAW"
        print(f"Test Case: {test_case}")
        lsu_latch.push({"addr_val": 0x0002_4400, "rw_mode": "write", "size": "word", "store_value": 0xDEAD_BEEF})    # Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0002_4400, "rw_mode": "write", "size": "word", "store_value": 0xBEEF_DEAD})    # Bank0
        run_sim(total_cycles, 24)
        total_cycles += 24
        print_banks()


    """
    7. TEST CASE Sec_Miss_B0_s4 - WAR
    The same UUID should be sent from the cache to the LSU to alert LSU that two missed requests have merged into one
    The LSU will need to assume that a new read request to the address will read the newly written value
    """
    with open("7.Sec_Miss_B0_s4_WAR.txt", "w") as f:
        sys.stdout = f
        test_case = "Sec_Miss_B0_s4 - WAR"
        print(f"Test Case: {test_case}")
        lsu_latch.push({"addr_val": 0x0002_6400, "rw_mode": "read", "size": "word"})    # Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0002_6400, "rw_mode": "write", "size": "word", "store_value": 0xBBBB_BBBB})    # Bank0
        run_sim(total_cycles, 24)
        total_cycles += 24
        print_banks()


    """
    8. TEST CASE MSHR_Full_b0
    """
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    with open("8.MSHR_Full_b0.txt", "w") as f:
        sys.stdout = f
        sys.stderr = f
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        # Add a new handler that writes to your file 'f'
        file_handler = logging.StreamHandler(f)
        formatter = logging.Formatter('%(levelname)s:%(message)s')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        root_logger.setLevel(logging.INFO) # Ensure INFO/WARNING logs are captured

        test_case = "MSHR_Full_b0"
        print(f"Test Case: {test_case}")
        lsu_latch.push({"addr_val": 0x0002_8400, "rw_mode": "read", "size": "word"})    # 1. Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0002_A400, "rw_mode": "read", "size": "word"})    # 2. Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0002_C400, "rw_mode": "read", "size": "word"})    # 3. Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0002_E400, "rw_mode": "read", "size": "word"})    # 4. Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0003_0400, "rw_mode": "read", "size": "word"})    # 5. Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0003_2400, "rw_mode": "read", "size": "word"})    # 6. Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0003_4400, "rw_mode": "read", "size": "word"})    # 7. Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0003_6400, "rw_mode": "read", "size": "word"})    # 8. Bank0. This causes victim ejection of 0x26400
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0003_8400, "rw_mode": "read", "size": "word"})    # 9 Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0003_A400, "rw_mode": "read", "size": "word"})    # 10 Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0003_C400, "rw_mode": "read", "size": "word"})    # 11 Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0003_E400, "rw_mode": "read", "size": "word"})    # 12 Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0004_0400, "rw_mode": "read", "size": "word"})    # 13 Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0004_2400, "rw_mode": "read", "size": "word"})    # 14 Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0004_4400, "rw_mode": "read", "size": "word"})    # 15 Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0004_6400, "rw_mode": "read", "size": "word"})    # 16 Bank0
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0004_8400, "rw_mode": "read", "size": "word"})    # 17 Bank0
        run_sim(total_cycles, 151)
        total_cycles += 151
        print_banks()

    sys.stdout = original_stdout
    sys.stderr = original_stderr
    
    # Remove the file handler (which is now closed and dangerous)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    # Restore the original console handlers
    for handler in original_handlers:
        root_logger.addHandler(handler)

    """
    9. TEST CASE Vic_eject_b0_s1
    """
    with open("9.Vic_eject_b0_s1.txt", "w") as f:
        sys.stdout = f
        logging.getLogger().setLevel(logging.WARNING)
        test_case = "Vic_eject_b0_s1"
        print(f"Test Case: {test_case}")
        lsu_latch.push({"addr_val": 0x0002_117C, "rw_mode": "read", "size": "word"})    # Bank0, set 1, word 7, ejects way 7 (LRU) 0x00010100, 0x0001017c should be deadbeef
        run_sim(total_cycles, 32)
        total_cycles += 32
        print_banks()
    

    """
    10. TEST CASE Seq_Hit_Miss
    """
    with open("10.Seq_Hit_Miss.txt", "w") as f:
        sys.stdout = f
        test_case = "Seq_Hit_Miss"
        print(f"Test Case: {test_case}")
        lsu_latch.push({"addr_val": 0x0002_2200, "rw_mode": "read", "size": "word"})    # Bank0 Miss
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0002_0200, "rw_mode": "read", "size": "word"})    # Bank0 Hit
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0002_3200, "rw_mode": "read", "size": "word"})    # Bank0 Miss
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0000_0000, "rw_mode": "read", "size": "word"})    # Bank0 Hit
        run_sim(total_cycles, 30)
        total_cycles += 30
        print_banks()
    

    """
    11. TEST CASE Seq_Hit_Hit
    """
    with open("11.Seq_Hit_Hit.txt", "w") as f:
        sys.stdout = f
        test_case = "Seq_Hit_Hit"
        print(f"Test Case: {test_case}")
        lsu_latch.push({"addr_val": 0x0000_0000, "rw_mode": "read", "size": "word"})    # Hit
        run_sim(total_cycles, 1)
        total_cycles += 1
        lsu_latch.push({"addr_val": 0x0000_0004, "rw_mode": "read", "size": "word"})    # Hit
        run_sim(total_cycles, 5)
        total_cycles += 5
        print_banks()
    

    """
    12. TEST CASE Read_Half_Word
    """
    with open("12.Read_Half_Word.txt", "w") as f:
        sys.stdout = f
        test_case = "Read_Half_Word"
        print(f"Test Case: {test_case}")
        lsu_latch.push({"addr_val": 0x00000000, "rw_mode": "read", "size": "half"}) # Expecting 0x0000_01D8
        run_sim(total_cycles, 3)
        total_cycles += 3
        print_banks()
    

    """
    13. TEST CASE Read_Byte
    """
    with open("13.Read_Byte.txt", "w") as f:
        sys.stdout = f
        test_case = "Read_Byte"
        print(f"Test Case: {test_case}")
        lsu_latch.push({"addr_val": 0x00000000, "rw_mode": "read", "size": "byte"}) # Expecting 0x0000_00D8
        run_sim(total_cycles, 3)
        total_cycles += 3
        print_banks()
    

    """
    14. TEST CASE Write_Half_Word
    """
    with open("14.Write_Half_Word.txt", "w") as f:
        sys.stdout = f
        test_case = "Write_Half_Word"
        print(f"Test Case: {test_case}")
        lsu_latch.push({"addr_val": 0x00000000, "rw_mode": "write", "size": "half", "store_value": 0xBEEF}) # Expecting 0x807D_BEEF
        run_sim(total_cycles, 3)
        total_cycles += 3
        print_banks()
    

    """
    15. TEST CASE Write_Byte
    """
    with open("15.Write_Byte.txt", "w") as f:
        sys.stdout = f
        test_case = "Write_Byte"
        print(f"Test Case: {test_case}")
        lsu_latch.push({"addr_val": 0x00000000, "rw_mode": "write", "size": "byte", "store_value": 0xBE}) # Expecting 0x807D_BEBE
        run_sim(total_cycles, 3)
        total_cycles += 3
        print_banks()
    
    """
    17. TEST CASE: icache and dcache request simultaneously
    Ensure that the cache can handle the backpressure from the memory controller
    """
    with open("17.icache_dcache.txt", "w") as f:
        sys.stdout = f
        test_case = "icache and dcache request simultaneously"
        print(f"Test Case: {test_case}")
        lsu_latch.push({"addr_val": 0x0000_1000, "rw_mode": "read", "size": "word"})
        run_sim(total_cycles, 17)
        total_cycles += 17
        ic_req.push({"addr": 0x0000_8000, "size": 128, "uuid": 999, "warp": 0, "rw_mode": "read", "src": "icache"})
        run_sim(total_cycles, 13)
        total_cycles += 13
        print_banks()
        

    """
    16. TEST CASE Halt
    Check that memsim.hex has been updated to the dirty values
    """
    with open("16.Halt.txt", "w") as f:
        sys.stdout = f
        test_case = "Halt"
        print(f"Test Case: {test_case}")
        lsu_latch.push({"halt": True}) # Expecting 0x00BE_7842
        run_sim(total_cycles, 90)
        total_cycles += 90
        print_banks()
