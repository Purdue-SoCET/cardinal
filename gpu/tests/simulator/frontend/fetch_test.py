import sys
from pathlib import Path

gpu_sim_root = Path(__file__).resolve().parents[3]
sys.path.append(str(gpu_sim_root))


from simulator.base_class import LatchIF
from common.custom_enums_multi import Instr_Type, R_Op, I_Op, F_Op, S_Op, B_Op, U_Op, J_Op, P_Op, H_Op
from common.custom_enums import Op
from simulator.src.scheduler.scheduler import SchedulerStage
from simulator.src.mem.icache_stage import ICacheStage
from simulator.src.mem.mem_controller import MemController
from simulator.src.mem.Memory import Mem
from simulator.base_class import *

START_PC = 0
LAT = 5
WARP_COUNT = 6

tbs_ws_if = LatchIF("Thread Block Scheduler - Warp Scheduler Latch")
sched_icache_if = LatchIF("Sched-ICache Latch")
icache_mem_req_if = LatchIF("ICache-Mem Latch")
dummy_dcache_mem_req_if = LatchIF("Dummy DCache-Mem Latch")
mem_icache_resp_if = LatchIF("Mem-ICache Latch")
dummy_dcache_mem_resp_if = LatchIF("Mem-Dummy DCache Latch")
icache_decode_if = LatchIF("ICache-Decode Latch")
decode_scheduler_fwif = ForwardingIF(name = "decode_forward_if")
issue_scheduler_fwif = ForwardingIF(name = "issue_forward_if")
branch_scheduler_fwif = ForwardingIF(name = "branch_forward_if")
writeback_scheduler_fwif = ForwardingIF(name = "Writeback_forward_if")

mem = Mem(
    start_pc=0x1000,
    input_file="/home/shay/a/sing1018/Desktop/SoCET_GPU_FuncSim/gpu/gpu/tests/simulator/frontend/test.bin",
    fmt="bin",
)

memc = MemController(
    name="Mem_Controller",
    ic_req_latch=icache_mem_req_if,
    dc_req_latch=dummy_dcache_mem_req_if,
    ic_serve_latch=mem_icache_resp_if,
    dc_serve_latch=dummy_dcache_mem_resp_if,
    mem_backend=mem, 
    latency=LAT,
    policy="rr"
)

scheduler_stage = SchedulerStage(
    name="Scheduler_Stage",
    behind_latch=tbs_ws_if,
    ahead_latch=sched_icache_if,
    forward_ifs_read= {"Decode_Scheduler" : decode_scheduler_fwif, "Issue_Scheduler": issue_scheduler_fwif, "Branch_Scheduler": branch_scheduler_fwif, "Writeback_Scheduler": writeback_scheduler_fwif},
    forward_ifs_write=None,
    start_pc=START_PC, 
    warp_count=WARP_COUNT
)

icache_stage = ICacheStage(
    name="ICache_Stage",
    behind_latch=sched_icache_if,
    ahead_latch=icache_decode_if,
    mem_req_if=icache_mem_req_if,
    mem_resp_if=mem_icache_resp_if,
    cache_config={"cache_size": 32 * 1024, 
                    "block_size": 64, 
                    "associativity": 4},
    forward_ifs_write= {"Decode_ICache_Ihit": decode_scheduler_fwif},
)

def dump_latches():
    def s(l): 
        return f"{l.name}: valid={l.valid} payload={type(l.payload).__name__ if l.payload else None}"
    print("TBS:")
    print("  ", s(tbs_ws_if))
    print("Scheduler:")
    print("  ", s(sched_icache_if))
    print("ICache:")
    print("  ", s(icache_mem_req_if))
    print("MEM->ICache:")
    print("  ", s(mem_icache_resp_if))
    print("ICache->Decode:")
    print("  ", s(icache_decode_if))

def step(cycle_num: int):
    print(f"\n--- Cycle {cycle_num} ---")
    memc.compute()
    icache_stage.compute()
    scheduler_stage.compute()
    dump_latches()
    if icache_decode_if.valid:
        instr = icache_decode_if.pop()
        print(f"ICache to Decode Instruction: {instr}")

def cycle(cycles = scheduler_stage.warp_count):
    for i in range(cycles):
        group, warp, pc = scheduler_stage.compute()
    return group, warp, pc

def test_fetch(LAT=10, START_PC=0, WARP_COUNT=6):
    print("Scheduler to ICacheStage Requests Test")

    warp_id = 0
    total_cycles = 15

    for c in range(1, total_cycles + 1):

        # Try to inject ONE warp request when the latch is free
        if warp_id < WARP_COUNT and tbs_ws_if.ready_for_push():
            dump_latches()
            req = {"type": DecodeType.MOP, "warp_id": warp_id, "pc": START_PC + warp_id * 4}
            ok = tbs_ws_if.push(req)
            assert ok
            warp_id += 1

        step(c)
 
  
if __name__ == "__main__":
    test_fetch()

