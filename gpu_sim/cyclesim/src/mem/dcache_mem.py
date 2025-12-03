#!/usr/bin/env python3
import sys
import os
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from collections import deque
from dcache import LockupFreeCacheStage
from base import *
from mem import MemStage, Mem

BLOCK_SIZE_WORDS = 32

# Cache to memory interface
dCacheMemReqIF = LatchIF(name="dCacheMemReqIF")
memReqdCacheIF = LatchIF(name="memReqdCacheIF")

# LSU to Cache interface
LSU_dCache_IF = LatchIF(name="LSU_dCache_IF")
dCache_LSU_RESP_IF = ForwardingIF(name="DCache_LSU_Resp")

def make_test_pipeline():
    mem_backend = Mem(start_pc = 0x1000,
                      input_file = "/home/shay/a/zhan4650/Desktop/gpu_seniorDesign/gpu/gpu_sim/cyclesim/src/mem/test.bin",
                      fmt = "bin")

    dCache = LockupFreeCacheStage(name = "dCache",
                                  behind_latch = LSU_dCache_IF,    # Change this to dummy
                                  forward_ifs_write = {"DCache_LSU_Resp": dCache_LSU_RESP_IF},   # Change this to dummy
                                  mem_req_if = dCacheMemReqIF,
                                  mem_resp_if = memReqdCacheIF
                                  )

    memStage = MemStage(name = "Memory",
                        behind_latch = dCacheMemReqIF,
                        ahead_latch = memReqdCacheIF,
                        mem_backend = mem_backend
                        )
    
    for latch in [dCacheMemReqIF, memReqdCacheIF, LSU_dCache_IF]:
        latch.clear_all()
    
    return {
        "dCache": dCache,
        "mem": memStage,
        "latches": {
            "dcache_mem": dCacheMemReqIF,
            "mem_dcache": memReqdCacheIF,
            "LSU_dCache": LSU_dCache_IF,
        },
        "forward_if": dCache_LSU_RESP_IF
    }

def print_latch_states(latches, cycle, before_after):
    """Prints the content of all latches for the current cycle."""
    if (before_after == "before"):
        print(f"=== Latch State Before Cycle {cycle} ===")
    else:
        print(f"=== Latch State at End of Cycle {cycle} ===")
    
    for name, latch in latches.items():
        # Handle LatchIF (has .valid and .payload)
        if hasattr(latch, 'valid'):
            if latch.valid:
                print(f"  [{latch.name}] VALID: {latch.payload}")
            else:
                # Optional: Comment this out if you only want to see active data
                print(f"  [{latch.name}] Empty")
        
        # Handle ForwardingIF (has .payload but no .valid flag, usually)
        elif hasattr(latch, 'payload'):
            if latch.payload is not None:
                print(f"  [{latch.name}] VALID: {latch.payload}")
            else:
                print(f"  [{latch.name}] Empty")

def run_sim (start, cycles):
    for cycle in range(start, start+cycles):
        print(f"\n=== Cycle {cycle} ===")
        
        print_latch_states(all_interfaces, cycle, "before")
        dcache_input = lsu_latch.pop()
        dCache.compute(input_data = dcache_input)
        mem.compute(input_data = None)
        response = resp_if.pop()
        if response:
            msg_type = response.type
            uuid = response.uuid
            data = response.data
            if (msg_type == 'MISS_ACCEPTED'):
                print(f"[Cycle {cycle}] LSU Received: MISS ACCEPTED (UUID: {uuid})")
            elif (msg_type == 'HIT_COMPLETE'):
                print(f"[Cycle {cycle}] LSU Received: HIT COMPLETE (Data: {data})")
            elif (msg_type == 'MISS_COMPLETE'):
                print(f"[Cycle {cycle}] LSU Received: MISS COMPLETE (UUID: {uuid}) - Data is in cache")
            elif (msg_type == 'HIT_STALL'):
                print(f"[Cycle {cycle}] LSU Received: HIT STALL")
        print_latch_states(all_interfaces, cycle, "after")
    print(f"=== Test ended ===")
    return (cycles)

if __name__ == "__main__":
    with open("dcache_mem_output.txt", "w") as f:
        sys.stdout = f
        total_cycles = 0

        sim = make_test_pipeline()
        mem = sim["mem"]
        dCache = sim["dCache"]
        resp_if = sim["forward_if"]
        all_interfaces = sim["latches"]
        all_interfaces["DCache_LSU_Resp"] = sim["forward_if"]
        lsu_latch = sim["latches"]["LSU_dCache"]

        # Miss on 0x1000 (R)
        test_request = {
            "addr_val": 0x1000,
            "rw_mode": "write",
            "store_value": 0xDEADBEEF,
            "id": 1
        }
        lsu_latch.push(test_request)
        run_sim(total_cycles, 25)
        total_cycles += 25
        
        
        # Hit on 0x1000 (R)
        test_request = {
            "addr_val": 0x1000,
            "rw_mode": "read",
            "id": 2
        }
        lsu_latch.push(test_request)

        run_sim(total_cycles, 3)
        total_cycles += 3

        
        # Miss on 0x1080 (W)
        test_request = {
            "addr_val": 0x1080,
            "rw_mode": "write",
            "store_value": 0xDEADBEEF,
            "id": 3
        }
        lsu_latch.push(test_request)
        run_sim(total_cycles, 25)
        total_cycles += 25


        # Miss followed by a hit
        test_request = {
            "addr_val": 0x1100,
            "rw_mode": "read",
            "id": 4
        }
        lsu_latch.push(test_request)
        run_sim(total_cycles, 1)
        total_cycles += 1

        test_request = {
            "addr_val": 0x1080,
            "rw_mode": "read",
            "id": 5
        }
        lsu_latch.push(test_request)
        run_sim(total_cycles, 25)
        total_cycles += 25
        # Successfully returned a hit while processing the miss


        # Victim Eject
        test_request = {
            "addr_val": 0x2000,
            "rw_mode": "read",
            "id": 6
        }
        lsu_latch.push(test_request)
        run_sim(total_cycles, 1)
        total_cycles += 1

        test_request = {
            "addr_val": 0x3000,
            "rw_mode": "read",
            "id": 7
        }
        lsu_latch.push(test_request)
        run_sim(total_cycles, 33)
        total_cycles += 33

        test_request = {
            "addr_val": 0x4000,
            "rw_mode": "read",
            "id": 8
        }
        lsu_latch.push(test_request)
        run_sim(total_cycles, 1)
        total_cycles += 1

        test_request = {
            "addr_val": 0x5000,
            "rw_mode": "read",
            "id": 9
        }
        lsu_latch.push(test_request)
        run_sim(total_cycles, 1)
        total_cycles += 1

        test_request = {
            "addr_val": 0x6000,
            "rw_mode": "read",
            "id": 9
        }
        lsu_latch.push(test_request)
        run_sim(total_cycles, 1)
        total_cycles += 1
        
        test_request = {
            "addr_val": 0x7000,
            "rw_mode": "read",
            "id": 10
        }
        lsu_latch.push(test_request)
        run_sim(total_cycles, 1)
        total_cycles += 1

        test_request = {
            "addr_val": 0x8000,
            "rw_mode": "read",
            "id": 11
        }
        lsu_latch.push(test_request)
        run_sim(total_cycles, 55)
        total_cycles += 55

        # EVICTING BANK 0, WAY 7
        test_request = {
            "addr_val": 0x9000,
            "rw_mode": "read",
            "id": 12
        }
        lsu_latch.push(test_request)
        run_sim(total_cycles, 33)
        total_cycles += 33
        # Checked that memsim.hex contains the dirty values

        # Halt
        test_request = {
            "addr_val": 0x9000,
            "rw_mode": "read",
            "id": 13,
            "halt": True
        }
        lsu_latch.push(test_request)
        run_sim(total_cycles, 11)
        total_cycles += 11
        # Successfully flushed and wrote dirty data back to memsim.hex


        for bank_id, bank in enumerate(dCache.banks):
            print(f"\n======== Bank {bank_id} ========")
            found_valid_line = False

            for set_id, cache_set in enumerate(bank.sets):
                # Check if the set has any valid lines
                set_has_valid_lines = any(frame.valid for frame in cache_set)

                if set_has_valid_lines:
                    found_valid_line = True
                    print(f"  ---- Set {set_id} ----")

                    # Print LRU order (Most Recently Used -> Least Recently Used)
                    lru_list = bank.lru[set_id]
                    print(f"    LRU Order: {lru_list} (Front=MRU, Back=LRU)")

                    for way_id, frame in enumerate(cache_set):
                        if frame.valid:
                            tag_hex = f"0x{frame.tag:X}"
                            dirty_str = "D" if frame.dirty else " "

                            print(f"    [Way {way_id}] V:1 {dirty_str} Tag: {tag_hex:<8}")

                            # Print data in rows of 4 words
                            for i in range(0, BLOCK_SIZE_WORDS, 4):
                                w0 = f"0x{frame.block[i]:08X}"
                                w1 = f"0x{frame.block[i+1]:08X}"
                                w2 = f"0x{frame.block[i+2]:08X}"
                                w3 = f"0x{frame.block[i+3]:08X}"
                                print(f"        Block[{i:02d}:{i+3:02d}]: {w0} {w1} {w2} {w3}")

            if not found_valid_line:
                print(f"  (Bank is empty)")
