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
from gpu.simulator.src.mem.ld_st import Ldst_Fu

BLOCK_SIZE_WORDS = 32       # 32 words per cache block

# Cache to memory interface
dcache_mem_req_IF = LatchIF(name="dcache_mem_req_IF")
mem_dcache_req_IF = LatchIF(name="mem_dcache_req_IF")

# LSU to Cache interface
lsu_dcache_IF = LatchIF(name="lsu_dcacheIF")
dcache_lsu_resp_IF = ForwardingIF(name="dcache_lsu_resp_IF")
lsu_dcache_IF.forward_if = dcache_lsu_resp_IF # LSU uses lsu_dcache_if.forward_if to access dcache_lsu_if if, can change if needed

# LSU, issue, scheduling and writeback interfaces
issue_lsu_IF = LatchIF("issue_lsu_IF")          # Issue --> LSU
lsu_issue_resp_IF = ForwardingIF(name="lsu_issue_resp_IF")
issue_lsu_IF.forward_if = lsu_issue_resp_IF
lsu_wb_IF = LatchIF("lsu_wb_IF")                # LSU --> Writeback Buffer
lsu_sched_IF = ForwardingIF(name="lsu_resp_IF")      # LSU --> Scheduling (for memory stalls)
lsu_wb_IF.forward_if = lsu_sched_IF

# iCache interfaces
ic_req = LatchIF("ICacheMemReqIF")
ic_resp = LatchIF("ICacheMemRespIF")

def make_test_pipeline():
    """
    This function connects creates the memory and dcache objects and connects the interfaces between them. It returns the objects and the interfaces (including the latches and "forwarding")
    """
    print(f"Initializing mem_backend with input file: {os.path.join(project_root, "gpu/tests/simulator/memory/dcache/test.bin")}")
    mem_backend = Mem(start_pc = 0x0000_0000,
                      input_file = os.path.join(project_root, "gpu/tests/simulator/memory/dcache/test.bin"),
                      fmt = "bin")

    dCache = LockupFreeCacheStage(name = "dCache",
                                  behind_latch = lsu_dcache_IF,    # Change this to dummy
                                  forward_ifs_write = {"DCache_LSU_Resp": dcache_lsu_resp_IF},   # Change this to dummy
                                  mem_req_if = dcache_mem_req_IF,
                                  mem_resp_if = mem_dcache_req_IF
                                  )

    memStage = MemController(name = "Memory",
                             ic_req_latch = ic_req,
                             dc_req_latch = dcache_mem_req_IF,
                             ic_serve_latch = ic_resp,
                             dc_serve_latch = mem_dcache_req_IF,
                             mem_backend = mem_backend,
                             latency = 5,
                             policy = "rr"
                            )
    
    lsu = Ldst_Fu(wb_buffer_size = 4)
    lsu.connect_interfaces(dcache_if=lsu_dcache_IF, wb_if=lsu_wb_IF, sched_if=issue_lsu_IF)
    
    for latch in [dcache_mem_req_IF, mem_dcache_req_IF, lsu_dcache_IF, ic_req, ic_resp, issue_lsu_IF, lsu_wb_IF]:
        latch.clear_all()
    
    return {
        "dCache": dCache,
        "mem": memStage,
        "lsu": lsu,
        "latches": {
            "issue_lsu_req": issue_lsu_IF,
            "LSU_dCache": lsu_dcache_IF,
            "dcache_mem": dcache_mem_req_IF,
            "mem_dcache": mem_dcache_req_IF,
            "lsu_wb_resp": lsu_wb_IF,
            "icache_mem_req": ic_req,
            "mem_icache_resp": ic_resp
        },
        "forward_latches": {
            "dcache_lsu_forward_if": lsu_dcache_IF.forward_if,
            "lsu_sched_forward_if": lsu_sched_IF
        }
    }

def print_latch_states(latches, forward_latches, cycle, before_after):
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
    
    print(f"\nForward latches:")
    for name, forward_latch in forward_latches.items():
        payload = None

        if hasattr(forward_latch, 'valid') and latch.valid:
            payload = forward_latch.payload
        elif hasattr(forward_latch, 'payload') and latch.payload is not None:
            payload = forward_latch.payload
            
        if payload is not None:
            # Print the formatted version
            print(f"  [{name}] VALID: {format_payload(payload)}")
        else:
            # Optional: Comment out to hide empty latches
            print(f"  [{name}] Empty")

def run_sim (start, cycles):
    '''
    Runs simulation by feeding LSQ each instr in instrs

    TODO: make run until lsq recieves flush confirmation
    '''
    for cycle in range(start, start+cycles):
        print(f"\n=== Cycle {cycle} ===")

        mem.compute(input_data = None)
        dCache.compute()
        lsu.tick(issue_if = issue_lsu_IF)

        dcache_response = dcache_lsu_resp_IF.payload
        if dcache_response:
            msg_type = dcache_response.type
            uuid = dcache_response.uuid
            data = dcache_response.data

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

        print_latch_states(all_interfaces, all_forward, cycle, "after")
        
        dcache_lsu_resp_IF.pop()
        lsu_response = lsu_wb_IF.pop()
        if (lsu_response):
            print(f"[Cycle {cycle}] WB Received instruction from LSU")
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
                            # FIX: Add '& 0xFFFFFFFF' to force unsigned 32-bit representation
                            w0 = f"0x{(frame.block[i] & 0xFFFFFFFF):08X}"
                            w1 = f"0x{(frame.block[i+1] & 0xFFFFFFFF):08X}"
                            w2 = f"0x{(frame.block[i+2] & 0xFFFFFFFF):08X}"
                            w3 = f"0x{(frame.block[i+3] & 0xFFFFFFFF):08X}"
                            
                            print(f"        Block[{i:02d}:{i+3:02d}]: {w0} {w1} {w2} {w3}")

        if not found_valid_line:
            print(f"  (Bank is empty)")

# PULLED FROM THE TESTS FOR LSU. Modified to fit the updated naming convention and new testing framework
class TestLoadStoreUnit():
    def genLoad(self,
                pc: Bits,
                opcode: Bits,
                rd=Bits(int=0, length=32),
                rdat1 = [Bits(int=0, length=32) for i in range(32)],
                rdat2 =  [Bits(int=0, length=32) for i in range(32)],
                wdat = [Bits(int=0, length=32) for i in range(32)],
                pred = [Bits(uint=1, length=1) for i in range(32)]
            ) -> Instruction:
        instr = Instruction(pc=pc,
                            intended_FU="ldst",
                            warp_id=0,
                            warp_group_id=0,
                            rs1=Bits(int=0,length=32),
                            rs2=Bits(int=0,length=32),
                            rd=rd,
                            wdat=wdat,
                            opcode=opcode,
                            rdat1 = rdat1,
                            rdat2 = rdat2,
                            predicate=pred
                            )
        return instr
    
    def genStore(self,
                pc: Bits,
                opcode: Bits,
                rd=Bits(int=0, length=32),
                rdat1 = [Bits(int=0, length=32) for i in range(32)],
                rdat2 =  [Bits(int=0, length=32) for i in range(32)],
                wdat = [Bits(int=0, length=32) for i in range(32)],
                pred = [Bits(uint=1, length=1) for i in range(32)]
            ) -> Instruction:
        instr = Instruction(pc=pc,
                            intended_FU="ldst",
                            warp_id=0,
                            warp_group_id=0,
                            rs1=Bits(int=0,length=32),
                            rs2=Bits(int=0,length=32),
                            rd=rd,
                            wdat=wdat,
                            opcode=opcode,
                            rdat1 = rdat1,
                            rdat2 = rdat2,
                            predicate=pred
                            )
        return instr
    
    def tickLdSt(self):
        instr = lsu.tick(issue_lsu_IF)
        if instr:
            lsu_wb_IF.push(instr)

# TEST LOAD WORD
def test_lw():
    with open("1.lw", "w") as f:
        sys.stdout = f
        test = TestLoadStoreUnit()
        instr = test.genLoad(pc=0, opcode=Bits(bin='0b0100000'), rd=0, rdat1 = [Bits(int=i, length=32) for i in range(0, 0x400, 32)])
        issue_lsu_IF.push(instr)
        run_sim(0, 220)

# TEST LOAD HALF-WORD
def test_lh():
    with open("2.lh", "w") as f:
        sys.stdout = f
        test = TestLoadStoreUnit()
        instr = test.genLoad(pc=0, opcode=Bits(bin='0b0100001'), rd=0, rdat1 = [Bits(int=i, length=32) for i in range(0, 0x400, 32)])
        issue_lsu_IF.push(instr)
        run_sim(0, 162)

# TEST BYTE
def test_lb():
    with open("3.lb", "w") as f:
        sys.stdout = f
        test = TestLoadStoreUnit()
        instr = test.genLoad(pc=0, opcode=Bits(bin='0b0100010'), rd=0, rdat1 = [Bits(int=i, length=32) for i in range(0, 0x400, 32)])
        issue_lsu_IF.push(instr)
        run_sim(0, 162)

# TEST STORE WORD
def test_sw():
    with open("4.sw", "w") as f:
        sys.stdout = f
        test = TestLoadStoreUnit()
        instr = test.genStore(pc=0, opcode=Bits(bin='0b0110000'), rd=0, rdat1 = [Bits(int=i, length=32) for i in range(0, 0x400, 32)], rdat2 = [Bits(uint=0xDEAD0000, length=32) for _ in range(32)])
        issue_lsu_IF.push(instr)
        run_sim(0, 162)
        print_banks()


# TEST STORE HALF-WORD
def test_sh():
    with open("5.store_half", "w") as f:
        sys.stdout = f
        test = TestLoadStoreUnit()
        instr = test.genStore(pc=0, opcode=Bits(bin='0b0110001'), rd=0, rdat1 = [Bits(int=i, length=32) for i in range(0, 0x400, 32)], rdat2 = [Bits(uint=0xBEEF, length=32) for _ in range(32)])
        issue_lsu_IF.push(instr)
        run_sim(0, 162)
        print_banks()


# TEST STORE BYTE
def test_sb():
    with open("6.sb", "w") as f:
        sys.stdout = f
        test = TestLoadStoreUnit()
        instr = test.genStore(pc=0, opcode=Bits(bin='0b0110010'), rd=0, rdat1 = [Bits(int=i, length=32) for i in range(0, 0x400, 32)], rdat2 = [Bits(uint=0xBE, length=32) for _ in range(32)])
        issue_lsu_IF.push(instr)
        run_sim(0, 162)
        print_banks()


# TEST PREDICATE
def test_pred():
    with open("7.test_pred", "w") as f:
        sys.stdout = f
        test = TestLoadStoreUnit()
        pred = [Bits(bin='0b0') for i in range(32)]
        pred[0] = Bits(bin='0b1')
        instr = test.genLoad(pc=0, opcode=Bits(bin='0b0100000'), rd=0, rdat1 = [Bits(int=i, length=32) for i in range(0, 0x400, 32)], pred = pred)
        issue_lsu_IF.push(instr)
        run_sim(0, 7)
        

# TEST BACKPRESSURE
def test_backpressure():
     with open("8.back_pressure", "w") as f:
        sys.stdout = f
        test = TestLoadStoreUnit()

        def gen_addrs(start):
            return [Bits(int=addr, length=32) for addr in range(start, start + (32*32), 32)]
                                                                
        # Instr. 1
        instr = test.genLoad(pc=0, opcode=Bits(bin='0b0100000'), rd=0, rdat1 = gen_addrs(0x0))
        issue_lsu_IF.push(instr)
        run_sim(0, 1)

        # Instr. 2
        instr = test.genLoad(pc=0, opcode=Bits(bin='0b0100000'), rd=0, rdat1 = gen_addrs(0x20))
        issue_lsu_IF.push(instr)
        run_sim(1, 1)

        # Instr. 3
        instr = test.genLoad(pc=0, opcode=Bits(bin='0b0100000'), rd=0, rdat1 = gen_addrs(0x40))
        issue_lsu_IF.push(instr)
        run_sim(2, 1)

        # Instr. 4
        instr = test.genLoad(pc=0, opcode=Bits(bin='0b0100000'), rd=0, rdat1 = gen_addrs(0x60))
        issue_lsu_IF.push(instr)
        run_sim(3, 4)

        # Instr. 5: Causes backpressure
        current_cycle = 7
        while (not issue_lsu_IF.ready_for_push()):
            run_sim(current_cycle, 1)
            current_cycle += 1
            pass
        instr = test.genLoad(pc=0, opcode=Bits(bin='0b0100000'), rd=0, rdat1 = gen_addrs(0x80))
        issue_lsu_IF.push(instr)
        run_sim(current_cycle, 670)
        print_banks()

# TEST HALT
def test_halt():
    with open("9.back_halt", "w") as f:
        sys.stdout = f
        test = TestLoadStoreUnit()
        instr = test.genLoad(pc=0, opcode=Bits(bin='0b1111111'), rd=0, rdat1 = [Bits(int=i, length=32) for i in range(0, 0x400, 32)])
        issue_lsu_IF.push(instr)
        run_sim(0, 46)
        print_banks()


if __name__ == "__main__":
    total_cycles = 0
    sim = make_test_pipeline()
    mem = sim["mem"]
    dCache = sim["dCache"]
    lsu = sim["lsu"]
    all_interfaces = sim["latches"]
    all_forward = sim["forward_latches"]
    test_lw()
    test_lh()
    test_lb()
    test_sw()
    test_sh()
    test_sb()
    test_pred()
    test_backpressure()
    test_halt()
