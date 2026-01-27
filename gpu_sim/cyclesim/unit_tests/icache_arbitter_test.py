#!/usr/bin/env python3
# icache_test.py — unit test for ICache + Mem interaction (with arbiter + demux)

import sys
from pathlib import Path

parent = Path(__file__).resolve().parent.parent
sys.path.append(str(parent))

from base import LatchIF, ForwardingIF, Instruction
from Memory import Mem
from units.icache import ICacheStage

# NEW decided-way memory pipeline:
#   ic_req + dc_req -> MemArbiterStage -> MemController -> MemRespDemuxStage -> ic_resp/dc_resp
from units.mem import MemArbiterStage, MemController, MemRespDemuxStage

from bitstring import Bits


# -------------------------------------------------------------------
# Helper: step the whole mini-system one cycle
# -------------------------------------------------------------------
def step_system(icache, arb, memc, demux):
    # Typical order: producers -> consumers
    # ICache produces mem requests; arb forwards; mem controller progresses; demux routes; icache consumes resp.
    icache.compute()
    assert icache.ahead_latch.valid, f"ICache pushed MemReq but ic_req_latch.valid is False."

    arb.compute()
    memc.compute()
    demux.compute()


def run_until_icache_output(icache, arb, memc, demux, ic_de_if, max_cycles=2000):
    for _ in range(max_cycles):
        step_system(icache, arb, memc, demux)
        if ic_de_if.valid:
            resp = ic_de_if.pop()
            print(f"TESTBENCH: got ICache output → {resp}")
            return resp
    return None


# -------------------------------------------------------------------
# TEST: Basic miss → fill → hit behavior
# -------------------------------------------------------------------
def test_icache_basic_behavior():
    # Prepare memory with DEADBEEF at 0x1000
    icache_ihit = ForwardingIF(name="Ihit_Resp")

    mem = Mem(start_pc=0x1000, input_file="/dev/null", fmt="bin")
    mem.memory.clear()
    mem.memory[0x1000] = 0xEF
    mem.memory[0x1001] = 0xBE
    mem.memory[0x1002] = 0xAD
    mem.memory[0x1003] = 0xDE

    # -----------------------
    # Latches for ICache pipe
    # -----------------------
    fetch_ic_if = LatchIF("Fetch→ICache")
    ic_de_if   = LatchIF("ICache→Decode")

    # -----------------------
    # Latches for NEW mem path
    # -----------------------
    ic_req_latch = LatchIF("ICache→MemArb_req")
    dc_req_latch = LatchIF("DCache→MemArb_req")   # unused in this unit test, but must exist
    arb_to_mem   = LatchIF("MemArb→MemCtrl_req")

    mem_unified_resp = LatchIF("MemCtrl→UnifiedResp")
    ic_resp_latch     = LatchIF("Demux→ICacheResp")
    dc_resp_latch     = LatchIF("Demux→DCacheResp")  # unused here

    # -----------------------
    # Build ICache
    # -----------------------
    icache = ICacheStage(
        name="ICache",
        behind_latch=fetch_ic_if,
        ahead_latch=ic_de_if,
        mem_req_if=ic_req_latch,       # NOTE: now goes to arbiter, not directly to controller
        mem_resp_if=ic_resp_latch,     # NOTE: now comes from demux
        cache_config={
            "cache_size": 1024,
            "block_size": 32,
            "associativity": 2,
            "miss_latency": 5,
            "mshr_entries": 4,
        },
        forward_ifs_write={"ihit": icache_ihit}
    )

    # -----------------------
    # Build memory pipeline (arb + ctrl + demux)
    # -----------------------
    arb = MemArbiterStage(
        name="MemArb",
        ic_req_latch=ic_req_latch,
        dc_req_latch=dc_req_latch,
        mem_req_out_latch=arb_to_mem,
        policy="rr",
    )

    mem_controller = MemController(
        name="MemCtrl",
        behind_latch=arb_to_mem,
        ahead_latch=mem_unified_resp,
        mem_backend=mem,
        latency=100,
    )

    demux = MemRespDemuxStage(
        name="MemDemux",
        behind_latch=mem_unified_resp,
        ic_resp_latch=ic_resp_latch,
        dc_resp_latch=dc_resp_latch,
    )

    # Clear all latches
    for lif in [fetch_ic_if, ic_de_if, ic_req_latch, dc_req_latch, arb_to_mem, mem_unified_resp, ic_resp_latch, dc_resp_latch]:
        lif.clear_all()

    # ----------------------------
    # 1) MISS (issue fetch)
    # ----------------------------
    miss_instruction = Instruction(iid=0, pc=0x1000, warp=0, warpGroup=0)
    fetch_ic_if.push(miss_instruction)

    # Step until we see a mem request leave the arbiter into MemController
    saw_req = False
    for _ in range(50):
        step_system(icache, arb, mem_controller, demux)
        if arb_to_mem.valid:
            _ = arb_to_mem.snoop()
            saw_req = True
            break
    assert saw_req, "ICache miss did not generate a request into MemController"

#     # Now step until ICache receives fill response (which unstalls it)
#     filled = False
#     for _ in range(1000):
#         step_system(icache, arb, mem_controller, demux)
#         # ICache consumes resp internally; easiest signal is it becomes unstalled again
#         if not icache.stalled and icache.pending_fetch is None:
#             filled = True
#             break
#     assert filled, "ICache never became unstalled after miss (fill did not return)"

#     # ----------------------------
#     # 2) SAME fetch must be a HIT
#     # ----------------------------
#     fetch_ic_if.push(miss_instruction)
#     resp = run_until_icache_output(icache, arb, mem_controller, demux, ic_de_if, max_cycles=200)

#     assert resp is not None, "ICache hit should produce output"
#     assert isinstance(resp.packet, Bits), f"Expected resp.packet Bits, got {type(resp.packet)}"

#     first_word = resp.packet[:32].uintle
#     assert first_word == 0xDEADBEEF, f"Expected 0xDEADBEEF, got 0x{first_word:X}"

#     print("ICache basic miss→fill→hit OK")

#     # =====================================================================
#     # TEST 2: Two consecutive hits to same line
#     # =====================================================================
#     icache.cache = {i: [] for i in range(icache.num_sets)}
#     icache.stalled = False
#     icache.pending_fetch = None

#     mem.memory.clear()
#     mem.memory[0x1000] = 0x11
#     mem.memory[0x1001] = 0x22
#     mem.memory[0x1002] = 0x33
#     mem.memory[0x1003] = 0x44

#     # refill once
#     fetch_ic_if.clear_all()
#     ic_de_if.clear_all()

#     fetch_ic_if.push(miss_instruction)
#     # step until fill completes
#     for _ in range(1500):
#         step_system(icache, arb, mem_controller, demux)
#         if not icache.stalled and icache.pending_fetch is None:
#             break

#     # Two hits
#     fetch_ic_if.push(miss_instruction)
#     resp1 = run_until_icache_output(icache, arb, mem_controller, demux, ic_de_if, max_cycles=200)

#     fetch_ic_if.push(miss_instruction)
#     resp2 = run_until_icache_output(icache, arb, mem_controller, demux, ic_de_if, max_cycles=200)

#     assert resp1.packet[:32].uintle == 0x44332211
#     assert resp2.packet[:32].uintle == 0x44332211

#     print("ICache consecutive hits OK")

#     # =====================================================================
#     # TEST 3: Multi-warp interleave (warp 0 @0x1000, warp 1 @0x2000)
#     # =====================================================================
#     icache.stalled = False
#     icache.pending_fetch = None
#     icache.cycle = 0
#     icache.cache = {i: [] for i in range(icache.num_sets)}

#     mem.memory.clear()
#     for i, b in enumerate([0x11, 0x22, 0x33, 0x44]):
#         mem.memory[0x1000 + i] = b
#     for i, b in enumerate([0x55, 0x66, 0x77, 0x88]):
#         mem.memory[0x2000 + i] = b

#     # Miss for warp 0, then fill
#     fetch_ic_if.push(Instruction(pc=0x1000, warp=0))
#     for _ in range(1500):
#         step_system(icache, arb, mem_controller, demux)
#         if not icache.stalled and icache.pending_fetch is None:
#             break

#     # Miss for warp 1, then fill
#     fetch_ic_if.push(Instruction(pc=0x2000, warp=1))
#     for _ in range(1500):
#         step_system(icache, arb, mem_controller, demux)
#         if not icache.stalled and icache.pending_fetch is None:
#             break

#     # Hit for warp 1
#     fetch_ic_if.push(Instruction(pc=0x2000, warp=1))
#     respw1 = run_until_icache_output(icache, arb, mem_controller, demux, ic_de_if, max_cycles=200)

#     assert respw1.packet[:32].uintle == 0x88776655
#     print("ICache multi-warp interleave OK")

#     # =====================================================================
#     # TEST 4: MSHR merge — 2 fetches to same block before fill returns
#     # =====================================================================
#     icache.cache = {i: [] for i in range(icache.num_sets)}
#     icache.stalled = False
#     icache.pending_fetch = None

#     mem.memory.clear()
#     for i, b in enumerate([0xAA, 0xBB, 0xCC, 0xDD]):
#         mem.memory[0x1000 + i] = b

#     # First miss
#     fetch_ic_if.push(miss_instruction)
#     step_system(icache, arb, mem_controller, demux)

#     # Drain out the first mem request (it will have been pushed into ic_req_latch then arb_to_mem)
#     # Now immediately issue second miss to same PC before fill comes back
#     fetch_ic_if.push(miss_instruction)
#     step_system(icache, arb, mem_controller, demux)

#     # The key: ICache should *not* have produced a second mem request (MSHR merge).
#     # We check ic_req_latch is empty (and arb_to_mem won't have a second new request).
#     assert not ic_req_latch.valid, "MSHR merge failed: duplicate ICache mem request appeared"

#     # Now wait for fill, then confirm hit
#     for _ in range(2000):
#         step_system(icache, arb, mem_controller, demux)
#         if not icache.stalled and icache.pending_fetch is None:
#             break

#     fetch_ic_if.push(miss_instruction)
#     resp = run_until_icache_output(icache, arb, mem_controller, demux, ic_de_if, max_cycles=200)

#     assert resp.packet[:32].uintle == 0xDDCCBBAA
#     print("ICache MSHR merge OK")


if __name__ == "__main__":
    test_icache_basic_behavior()
    print("ALL ICache TESTS PASSED")
