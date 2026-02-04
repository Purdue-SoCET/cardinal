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
from simulator.src.decode.decode_class import DecodeStage
from simulator.src.decode.predicate_reg_file import PredicateRegFile
from simulator.base_class import *

START_PC = 4
LAT = 2
WARP_COUNT = 6

tbs_ws_if = LatchIF("Thread Block Scheduler - Warp Scheduler Latch")
sched_icache_if = LatchIF("Sched-ICache Latch")
icache_mem_req_if = LatchIF("ICache-Mem Latch")
dummy_dcache_mem_req_if = LatchIF("Dummy DCache-Mem Latch")
mem_icache_resp_if = LatchIF("Mem-ICache Latch")
dummy_dcache_mem_resp_if = LatchIF("Mem-Dummy DCache Latch")
icache_decode_if = LatchIF("ICache-Decode Latch")
decode_issue_if = LatchIF("Decode-Issue Latch")
icache_scheduler_fwif = ForwardingIF(name = "icache_forward_if")
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
    forward_ifs_read= {"ICache_Scheduler" : icache_scheduler_fwif, "Decode_Scheduler": decode_scheduler_fwif, "Issue_Scheduler": issue_scheduler_fwif, "Branch_Scheduler": branch_scheduler_fwif, "Writeback_Scheduler": writeback_scheduler_fwif},
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
    forward_ifs_write= {"ICache_scheduler_Ihit": icache_scheduler_fwif},
)

prf = PredicateRegFile(
    num_preds_per_warp=16,
    num_warps=16
)

decode_stage = DecodeStage(
    name="Decode Stage",
    behind_latch=icache_decode_if,
    ahead_latch=decode_issue_if,
    prf=prf,
    forward_ifs_read=None,
    forward_ifs_write={"D"}
)
def dump_sched_fwifs():
    print(" ")
    print("Icache: ", icache_scheduler_fwif)
    print("Decoder: ", decode_scheduler_fwif)
    print("Issue: ", issue_scheduler_fwif)
    print("Branch: ", branch_scheduler_fwif)
    print("Writeback: ", writeback_scheduler_fwif)

def dump_latches():
    def s(l): 
        return f"{l.name}: valid={l.valid} payload={type(l.payload).__name__ if l.payload else None}"
    print(" ")
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
    print(" ")

def call_stages(debug=False):
    # compute order is called in reverse: 
    # this is wrt. to cycle order: 0
    # 1) ICache taking a response back from MemController for -2 cycle
    # 2) MemController servicing requests from ICache for -1 cycle
    # 3) ICache issuing new requests to MemController for 0 cycle
    # 4) Warp Scheduler fetching instructions from ICache for 1 cycle
    # 5) TBS is going BS for t > 1 cycle

    # step #1: initiate computes to pass through dummy instructions
    # until we reach the first real fetch from TBS

    if (debug): 
        dump_latches()

    if icache_decode_if.valid: # should be ture if i didnt inject bs
        instr = icache_decode_if.pop()
        print(f"[dummy_DECODE] Received Instruction: {instr}")
    else:
        print("[dummy_DECODE] No instruction received.")

    if (debug):
        dump_latches()

    # icache_stage.compute() # Icache getting MemResp
    
    # if (debug):
    #     dump_latches()

    memc.compute() # MemController servicing ICache req
    if (debug):
        dump_latches()

    icache_stage.compute() # ICache issuing new MemReq
    if (debug):
        dump_latches()

    inst = scheduler_stage.compute() # Scheduler fetching from ICache
    if (debug):
        dump_latches()
        
    print(f"\nTBS fetched warp {inst.warp} group {inst.warpGroup} pc 0x{inst.pc:X}\n")

def cycle(cycles = scheduler_stage.warp_count):
    for i in range(cycles):
        group, warp, pc = scheduler_stage.compute()
    return group, warp, pc

def test_fetch(LAT=2, START_PC=4, WARP_COUNT=6):
    print("Scheduler to ICacheStage Requests Test")

    warp_id = 0
    total_cycles = 15


    # initializing all the latches and such
    tbs_ws_if.clear_all()
    sched_icache_if.clear_all()
    icache_mem_req_if.clear_all()
    dummy_dcache_mem_req_if.clear_all()
    mem_icache_resp_if.clear_all()
    dummy_dcache_mem_resp_if.clear_all()
    icache_decode_if.clear_all()

    # initialize the payload initially to what we expect,
    # or set some framework value for it in the pipeline
    # so it doesnt tweak out

    icache_scheduler_fwif.payload = None
    decode_scheduler_fwif.payload = None
    issue_scheduler_fwif.payload = None
    branch_scheduler_fwif.payload = None
    writeback_scheduler_fwif.payload = None

    # first set of instructions: fill in the pipeline. 
    dummy_Instruction = Instruction(
        iid=0,
        pc=Bits(uint=0, length=32),
        intended_FSU=None,
        warp=0,
    )

    sched_icache_dummy_Instruction = Instruction(
        iid=0,
        pc=Bits(uint=0, length=32),
        intended_FSU=None,
        warp=0,
        warpGroup=None
    )

    icache_mem_req_dummy_Instruction = {
            "addr": 0,
            "size": 4,
            "uuid": 0,
            "warp_id": 0,
            "pc": 0,
            "data": 0,
            "rw_mode": "read",
            "remaining": LAT
    }

    dummy_dcache_mem_req_Instruction = {
        "addr": 0,
        "size": 4,
        "uuid": 0,
        "warp_id": 0,
        "pc": 0,
        "data": 0,
        "rw_mode": "read",
        "remaining": LAT
    }

    mem_icache_resp_dummy_Instruction = Instruction(
        iid=0,
        pc=Bits(uint=0, length=32),
        intended_FSU=None,
        warp=0,
        warpGroup=None,
        packet=Bits(uint=0, length=32
        ))

    icache_decode_dummy_Instruction = Instruction(
        iid=0,
        pc=Bits(hex='ABABABAB', length=32),
        intended_FSU=None,
        warp=0,
        warpGroup=None,
        opcode=None,
        rs1=0,
        rs2=0,
        rd=0
    )

    # setup some bullshit at the beginning for the latches 
    # this is initializing the latches for ONE cycle.

    tbs_ws_if.push({"warp_id": warp_id, 
                    "pc": START_PC + warp_id * 4})

    
    call_stages(debug=False)  # cycle -2

    input("---- Press Enter to continue to cycle #2 ----")
    
    call_stages(debug=False)  # cycle -1

    input("---- Press Enter to continue to cycle #3 ----")
    
    call_stages(debug=False) # cycle 0

    input("---- Press Enter to continue to cycle #4 ----")
    
    call_stages(debug=False)  # cycle -1

    input("---- Press Enter to continue to cycle #5 ----")
    
    call_stages(debug=False) # cycle 0

    input("---- Press Enter to continue to cycle #5 ----")
    
    call_stages(debug=False) # cycle 1

    



if __name__ == "__main__":
    test_fetch()

