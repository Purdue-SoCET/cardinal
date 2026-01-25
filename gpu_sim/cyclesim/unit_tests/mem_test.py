# ================================================
# MemStage Unit Test Suite
# ================================================
import sys
from pathlib import Path

parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

from typing import Any, Dict, List, Optional
from base import ForwardingIF, LatchIF, Stage, Instruction, ICacheEntry, MemRequest, FetchRequest, DecodeType
from Memory import Mem
from units.mem import MemStage
from bitstring import Bits


# ------------------------------------------------
# Pipeline cycle helper (CORRECT)
# ------------------------------------------------
def run_cycles(stage, behind, ahead, cycles, collect_list=None):
    """
    Runs stage compute for N cycles.
    Simulates pipeline behavior:
    - stage.compute() runs once per cycle
    - ahead latch is auto-consumed (like a real next stage)
    - consumed values are printed clearly
    """

    for cycle in range(cycles):
        print(f"\n--- Cycle {cycle} ---")

        # Phase 1: The stage performs its compute()
        stage.compute()

        # Phase 2: Consumer stage reads the output latch
        if ahead.valid:
            resp = ahead.pop()

            # Pretty-print consumed value
            data_hex = resp["data"].hex if hasattr(resp["data"], "hex") else resp["data"]
            print(f"TESTBENCH: Auto-consuming ahead latch:")
            print(f"    → UUID={resp['uuid']}, data={data_hex}, warp={resp.get('warp')}")
            print(f"    (consumed at cycle {cycle})")

            # Store if requested
            if collect_list is not None:
                collect_list.append(resp)

# ------------------------------------------------------------
# TEST SUITE A — Binary file tests
# ------------------------------------------------------------
def test_memstage_with_binary():
    print("\n=== TEST SUITE A: Binary-based tests ===")

    mem_backend = Mem(
        start_pc=0x1000,
        input_file="/home/shay/a/sing1018/Desktop/SoCET_GPU_FuncSim/gpu/gpu_sim/cyclesim/drafts/test.bin",
        fmt="bin"
    )

    behind = LatchIF("ICacheMemReqIF_A")
    ahead  = LatchIF("MemICacheRespIF_A")

    mem_stage = MemStage(
        name="MemoryA",
        behind_latch=behind,
        ahead_latch=ahead,
        mem_backend=mem_backend,
        latency=3
    )

    # --------------------------
    # CASE 1: First word
    # --------------------------
    behind.push({"addr": 0x1000, "size": 4, "uuid": 1, "warp": 0})
    results = []
    run_cycles(mem_stage, behind, ahead, 4, results)
    assert results[-1]["uuid"] == 1
    print("First word =", results[-1]["data"].hex)

    # --------------------------
    # CASE 2: Middle word
    # --------------------------
    behind.push({"addr": 0x1000 + 40, "size": 4, "uuid": 2, "warp": 1})
    run_cycles(mem_stage, behind, ahead, 4, results)
    assert results[-1]["uuid"] == 2
    print("Middle word =", results[-1]["data"].hex)

    # --------------------------
    # CASE 3: Last word
    # --------------------------
    last_addr = max(mem_backend.memory.keys()) & ~0x3
    behind.push({"addr": last_addr, "size": 4, "uuid": 3, "warp": 0})
    run_cycles(mem_stage, behind, ahead, 4, results)
    assert results[-1]["uuid"] == 3
    print("Last word =", results[-1]["data"].hex)

    # --------------------------
    # CASE 4: Multiple inflight
    # --------------------------
    behind.push({"addr": 0x1000, "uuid": 10, "size": 4, "warp": 0})
    run_cycles(mem_stage, behind, ahead, 1, results)

    behind.push({"addr": 0x1004, "uuid": 11, "size": 4, "warp": 0})
    run_cycles(mem_stage, behind, ahead, 1, results)

    behind.push({"addr": 0x1008, "uuid": 12, "size": 4, "warp": 0})
    run_cycles(mem_stage, behind, ahead, 1, results)

    # finish them
    run_cycles(mem_stage, behind, ahead, 5, results)

    recent = [r["uuid"] for r in results[-3:]]
    assert set(recent) == {10, 11, 12}
    print("Multiple inflight PASS")

    # --------------------------
    # CASE 5: Variable sizes
    # --------------------------
    behind.push({"addr": 0x1000, "size": 1, "uuid": 20, "warp": 0})
    run_cycles(mem_stage, behind, ahead, 1, results)

    behind.push({"addr": 0x1001, "size": 2, "uuid": 21, "warp": 0})
    run_cycles(mem_stage, behind, ahead, 5, results)

    # The last two outputs are the ones we check
    assert results[-2]["data"].len == 8
    assert results[-1]["data"].len == 16
    print("Non-4-byte loads PASS")



# # ------------------------------------------------------------
# # TEST SUITE B — Manual Memory Tests
# # ------------------------------------------------------------
# def test_memstage_manual_memory():
#     print("\n=== TEST SUITE B: Manual memory tests ===")

#     mem_backend = Mem(start_pc=0x1000, input_file="/dev/null", fmt="bin")
#     mem_backend.memory.clear()

#     mem_backend.memory[0x1000] = 0xEF
#     mem_backend.memory[0x1001] = 0xBE
#     mem_backend.memory[0x1002] = 0xAD
#     mem_backend.memory[0x1003] = 0xDE

#     mem_backend.memory[0x2000] = 0x11
#     mem_backend.memory[0x2001] = 0x22
#     mem_backend.memory[0x2002] = 0x33
#     mem_backend.memory[0x2003] = 0x44

#     behind = LatchIF("ICacheMemReqIF_B")
#     ahead  = LatchIF("MemICacheRespIF_B")

#     mem_stage = MemStage(
#         name="MemoryB",
#         behind_latch=behind,
#         ahead_latch=ahead,
#         mem_backend=mem_backend,
#         latency=2
#     )

#     results = []

#     # C1 aligned
#     behind.push({"addr": 0x1000, "size": 4, "uuid": 100})
#     run_cycles(mem_stage, behind, ahead, 3, results)
#     print(results[-1]["data"].uint)
#     assert results[-1]["data"].uint == 0xDEADBEEF
#     print("Manual aligned load OK")

#     # C2 unaligned
#     behind.push({"addr": 0x1001, "size": 3, "uuid": 101})
#     run_cycles(mem_stage, behind, ahead, 3, results)
#     assert results[-1]["data"].hex == "beadde"
#     print("Unaligned load OK")

#     # C3 two requests
#     behind.push({"addr": 0x1000, "uuid": 105})
#     run_cycles(mem_stage, behind, ahead, 1, results)

#     behind.push({"addr": 0x2000, "uuid": 106})
#     run_cycles(mem_stage, behind, ahead, 1, results)

#     run_cycles(mem_stage, behind, ahead, 4, results)

#     # last 2 must be 105, 106
#     recent = [r["uuid"] for r in results[-2:]]
#     assert set(recent) == {105, 106}
#     print("Multiple outstanding OK")

#     # C4 missing bytes → zeros
#     behind.push({"addr": 0x3000, "uuid": 107, "size": 4})
#     run_cycles(mem_stage, behind, ahead, 3, results)
#     assert results[-1]["data"].uint == 0
#     print("Missing-byte load -> zero OK")



# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
if __name__ == "__main__":
    test_memstage_with_binary()
    print("\nALL TESTS PASSED.")
