# icache_test.py — Correct unit test for ICache + Mem interaction

import sys
from pathlib import Path

parent = Path(__file__).resolve().parent.parent
sys.path.append(str(parent))

from base import LatchIF, ForwardingIF, Stage, Instruction, ICacheEntry, dump_bytes
from Memory import Mem
from units.icache import ICacheStage   # ← your actual ICacheStage file
from units.mem import MemController
from bitstring import Bits


# -------------------------------------------------------------------
# Helper: simulate cycles
# -------------------------------------------------------------------
def run_stage(stage, behind, ahead, cycles=20):
    for cycle in range(cycles):
        stage.compute()
        if ahead.valid:
            resp = ahead.pop()
            print(f"TESTBENCH: Auto-consume → {resp}")
            return resp
    return None


# -------------------------------------------------------------------
# TEST: Basic miss → fill → hit behavior
# -------------------------------------------------------------------
def test_icache_basic_behavior():

    # Prepare memory with DEADBEEF at 0x1000
    icache_ihit = ForwardingIF(name = "Ihit_Resp")
    mem = Mem(start_pc=0x1000,
              input_file="/dev/null",
              fmt="bin",)

    mem.memory.clear()
    mem.memory[0x1000] = 0xEF
    mem.memory[0x1001] = 0xBE
    mem.memory[0x1002] = 0xAD
    mem.memory[0x1003] = 0xDE
    mem.memory
    
    # Build latches
    fetch_ic_if = LatchIF("Fetch→ICache")
    ic_de_if   = LatchIF("ICache→Decode")
    memreq_if  = LatchIF("ICache→Mem")
    memresp_if = LatchIF("Mem→ICache")

    # Build ICache
    icache = ICacheStage(
        name="ICache",
        behind_latch=fetch_ic_if,
        ahead_latch=ic_de_if,
        mem_req_if=memreq_if,
        mem_resp_if=memresp_if,
        cache_config={
            "cache_size": 1024,
            "block_size": 32,
            "associativity": 2,
            "miss_latency": 5,
            "mshr_entries": 4,
        },
        forward_ifs_write={"ihit": icache_ihit}
    )

    #  build Mem Controller
    mem_controller = MemController (
        name="Memory Controller",
        behind_latch=memreq_if,
        ahead_latch=memresp_if,
        mem_backend=mem,
        latency=100
    )

    memreq_if.clear_all()
    memresp_if.clear_all()
    fetch_ic_if.clear_all()
    ic_de_if.clear_all()

    # ----------------------------
    # 1) MISS
    # ----------------------------
    #create the instruction 
    miss_instruction = Instruction(
        iid=0, pc=0x1000, warp=0, warpGroup=0
    )
    fetch_ic_if.push(miss_instruction)

    icache.compute()
    assert memreq_if.valid
    # ----------------------------
    # 2) Simulate memory response
    # ----------------------------

    # should I in build the memory with the cache ?
    # run mem controller until it responds
    for _ in range(200):          # must be >= latency
        mem_controller.compute()
        if memresp_if.valid:
            break
    assert memresp_if.valid, "MemController never responded"

    icache.compute()   # handle fill

    # ----------------------------
    # 3) Now the SAME fetch must be a HIT
    # ----------------------------
    fetch_ic_if.push(miss_instruction)
    resp = run_stage(icache, fetch_ic_if, ic_de_if)

    assert resp is not None, "ICache hit should produce output"
    assert isinstance(resp.packet, Bits)

    # Confirm first 4 bytes = EF BE AD DE (little endian → DEADBEEF)
    first_word = resp.packet[:32].uintle
    assert first_word == 0xDEADBEEF, (
        f"Expected 0xDEADBEEF, got 0x{first_word:X}"
    )

    #Next series of tests for consecutive hits from the icache 
    # =====================================================================
    # TEST 2: Two consecutive hits to same line
    # =====================================================================
    icache.cache = {i: [] for i in range(icache.num_sets)}
    
    mem.memory.clear()
    mem.memory[0x1000] = 0x11
    mem.memory[0x1001] = 0x22
    mem.memory[0x1002] = 0x33
    mem.memory[0x1003] = 0x44

    print("CLEARED MEMORY, OVERWRITE FOR NEXT TEST\n")
    fetch_ic_if.push(miss_instruction)
    icache.compute()
    assert memreq_if.valid 

    # run mem controller until it responds
    for _ in range(101):          # must be >= latency
        mem_controller.compute()
        if memresp_if.valid:
            break
    assert memresp_if.valid, "MemController never responded"

    # now icache consumes response
    icache.compute()

    # Two HITS in a row
    fetch_ic_if.push(miss_instruction)
    resp1 = run_stage(icache, fetch_ic_if, ic_de_if)

    fetch_ic_if.push(miss_instruction)
    resp2 = run_stage(icache, fetch_ic_if, ic_de_if)

    assert resp1.packet[:32].uintle == 0x44332211
    assert resp2.packet[:32].uintle == 0x44332211

    print("ICache consecutive hits OK")


    # =====================================================================
    # TEST 3: Multi-warp interleave (warp 0 on 0x1000, warp 1 on 0x2000)
    # =====================================================================
    icache.stalled = False
    icache.pending_fetch = None
    
    icache.cycle = 0
    icache.cache = {i: [] for i in range(icache.num_sets)}

    mem.memory.clear()
    # block for warp 0
    for i, b in enumerate([0x11,0x22,0x33,0x44]):
        mem.memory[0x1000+i] = b
    # block for warp 1
    for i, b in enumerate([0x55,0x66,0x77,0x88]):
        mem.memory[0x2000+i] = b
    memreq_if.clear_all()
    memresp_if.clear_all()
    fetch_ic_if.clear_all()
    ic_de_if.clear_all()
    # Miss for warp 0
    fetch_ic_if.push(Instruction(pc=0x1000, warp=0))
    icache.compute()
    
    # run mem controller until it responds
    for _ in range(200):          # must be >= latency
        mem_controller.compute()
        if memresp_if.valid:
            break
    assert memresp_if.valid, "MemController never responded"

    # now icache consumes response
    icache.compute()

    # Miss for warp 1
    fetch_ic_if.push(Instruction(pc=0x2000,warp=1))
    icache.compute()
    # run mem controller until it responds
    for _ in range(200):          # must be >= latency
        mem_controller.compute()
        if memresp_if.valid:
            break
    assert memresp_if.valid, "MemController never responded"

    # now icache consumes response
    icache.compute()

    fetch_ic_if.push(Instruction(pc=0x2000,warp=1))
    resp1 = run_stage(icache, fetch_ic_if, ic_de_if)

    # assert resp0["packet"][:32].uintle == 0x44332211
    assert resp1.packet[:32].uintle == 0x88776655

    print("ICache multi-warp interleave OK")


    # =====================================================================
    # TEST 4: MSHR merge — 2 fetches to same block before fill returns
    # =====================================================================
    icache.cache = {i: [] for i in range(icache.num_sets)}
    
    mem.memory.clear()
    for i, b in enumerate([0xAA,0xBB,0xCC,0xDD]):
        mem.memory[0x1000+i] = b
    memreq_if.clear_all()
    memresp_if.clear_all()
    fetch_ic_if.clear_all()
    ic_de_if.clear_all()
    # First miss
    fetch_ic_if.push(miss_instruction)
    icache.compute()
    first_req = memreq_if.pop()
    assert first_req is not None

    # Second miss to the **same PC** — should NOT send new MemReq
    fetch_ic_if.push(miss_instruction)
    icache.compute()

    assert memreq_if.valid is False, "MSHR merge failed (duplicate MemReq)"

    # run mem controller until it responds
    for _ in range(400):          # must be >= latency
        mem_controller.compute()
        if memresp_if.valid:
            break
    assert memresp_if.valid, "MemController never responded"

    # now icache consumes response
    icache.compute()
    # After fill, hit
    fetch_ic_if.push(miss_instruction)
    resp = run_stage(icache, fetch_ic_if, ic_de_if)

    assert resp.packet[:32].uintle == 0xDDCCBBAA

    print("ICache MSHR merge OK")



if __name__ == "__main__":
    test_icache_basic_behavior()
    print("ALL ICache TESTS PASSED")
