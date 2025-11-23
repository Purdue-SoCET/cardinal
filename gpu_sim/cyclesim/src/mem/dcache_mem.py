#!/usr/bin/env python3
import sys
import os
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from collections import deque
from dcache_wip import LockupFreeCacheStage
from base import ForwardingIF, LatchIF, Stage, Addr, Instruction, MemRequest, dCacheFrame, MSHREntry
from dcache_wip import LockupFreeCacheStage
from mem import MemStage, Mem

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
            msg_type = response.get('type', 'UNKNOWN')
            if (msg_type == 'MISS_ACCEPTED'):
                uuid = response.get('uuid')
                print(f"[Cycle {cycle}] LSU Received: MISS ACCEPTED (UUID: {uuid})")
            elif (msg_type == 'HIT_COMPLETE'):
                data = response.get('data')
                print(f"[Cycle {cycle}] LSU Received: HIT COMPLETE (Data: {data})")
            elif (msg_type == 'MISS_COMPLETE'):
                uuid = response.get('uuid')
                print(f"[Cycle {cycle}] LSU Received: MISS COMPLETE (UUID: {uuid}) - Data is in cache")
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
        test_request = {
            "addr": 0x1000,
            "rw": "read",
            "id": 1
        }
        LSU_dCache_IF.push(test_request)
        run_sim(total_cycles, 25)
        total_cycles += 25

        test_request = {
            "addr": 0x1000,
            "rw": "read",
            "id": 2
        }
        LSU_dCache_IF.push(test_request)
        run_sim(total_cycles, 3)
        total_cycles += 3
