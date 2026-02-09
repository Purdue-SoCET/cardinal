import sys
from pathlib import Path

gpu_sim_root = Path(__file__).resolve().parents[3]
sys.path.append(str(gpu_sim_root))

from common.custom_enums_multi import *
from common.custom_enums import Op
from simulator.src.mem.icache_stage import ICacheStage
from simulator.src.mem.dcache_stage import LockupFreeCacheStage
from simulator.src.mem.mem_controller import MemController
from simulator.src.mem.Memory import Mem
from simulator.src.decode.decode_class import DecodeStage
from simulator.base_class import *

START_PC = 4
LAT = 2
WARP_COUNT = 6
BLOCK_SIZE_WORDS = 32

tbs_ws_if = LatchIF("Thread Block Scheduler - Warp Scheduler Latch")
sched_icache_if = LatchIf("Sched-Icache Latch")
icache_mem_req_if = LatchIF("ICache-Mem Latch")
dcache_mem_req_if = LatchIF("DCache-Mem Latch")
mem_icache_resp_if = LatchIF("Mem-ICache Latch")
mem_dcache_resp_if = LatchIF("Mem-DCache Latch")
lsu_dcache_if = LatchIF("Lsu-DCache Latch")
dcache_lsu_if = LatchIF("DCache-Lsu Latch")
icache_decode_if = LatchIF("ICache-Decode Latch")
decode_issue_if = LatchIF("Decode-Issue Latch")
dummy_issue_execute_if = LatchIF("Dummy Issue-Execute Latch")
# this can be set to some variable latency...
dummy_execute_writeback_if = LatchIF("Dummy Execute Writeback Latch")
dummy_writeback_rf = LatchIF("Dummy Writeback Latch")

dcache_lsu_resp_fwif = ForwardingIF("DCache-LSU FWIF")
icache_scheduler_fwif = ForwardingIF(name = "icache_forward_if")
decode_scheduler_fwif = ForwardingIF(name = "decode_forward_if")
issue_scheduler_fwif = ForwardingIF(name = "issue_forward_if")
branch_scheduler_fwif = ForwardingIF(name = "branch_forward_if")
writeback_scheduler_fwif = ForwardingIF(name = "Writeback_forward_if")

mem = Mem(
        start_pc=0x0,
        input_file="/home/shay/a/sing1018/Desktop/SoCET_GPU_FuncSim/gpu/gpu/tests/simulator/frontend/test.bin",
        fmt="bin",
    )

memc = MemController(
    name="Mem_Controller",
    ic_req_latch=icache_mem_req_if,
    dc_req_latch=dcache_mem_req_if,
    ic_serve_latch=mem_icache_resp_if,
    dc_serve_latch=dcache_mem_resp_if,
    mem_backend=mem, 
    latency=LAT,
    policy="rr"
)

icache_stage = ICacheStage(
    name="ICache_Stage",
    behind_latch=sched_icache_if,
    ahead_latch=icache_decode_if,
    mem_req_if=icache_mem_req_if,
    mem_resp_if=mem_icache_resp_if,
    cache_config={"cache_size": 32 * 1024, 
                    "block_size": 4, 
                    "associativity": 1},
    forward_ifs_write= {"ICache_scheduler_Ihit": icache_scheduler_fwif},
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

prf = PredicateRegFile(
    num_preds_per_warp=16,
    num_warps=16
)

decode_stage = DecodeStage(
    name="Decode Stage",
    behind_latch=icache_decode_if,
    ahead_latch=decode_issue_if,
    prf=prf,
    forward_ifs_read={"ICache_Decode_Ihit": icache_scheduler_fwif},
    forward_ifs_write={"Decode_Scheduler_Pckt": decode_scheduler_fwif}
)

dcache_stage = LockupFreeCacheStage(name="dCache",
                                    behind_latch=lsu_dcache_if,
                                    ahead_latch=dcache_lsu_if,
                                    mem_req_if=dcache_mem_req_if,
                                    mem_resp_if=mem_dcache_resp_if
                                    forward_ifs_write = {"DCache_LSU_Resp": dCache_lau_resp_if}
                                    )

def dump_sched_fwifs():
    print(" ")
    print("Icache: ", icache_scheduler_fwif)
    print("Decoder: ", decode_scheduler_fwif)
    print("Issue: ", issue_scheduler_fwif)
    print("Branch: ", branch_scheduler_fwif)
    print("Writeback: ", writeback_scheduler_fwif)
    print("LSU-DCache: ", dcache_lsu_resp_fwif()

def dump_latches():
    def s(l): 
        return f"{l.name}: valid={l.valid} payload={type(l.payload).__name__ if l.payload else None}"
    print(" ")
    print("TB<->Scheduler:")
    print("  ", s(tbs_ws_if))
    print("Scheduler<->ICache:")
    print("  ", s(sched_icache_if))
    print("ICache<->Mem:")
    print("  ", s(icache_mem_req_if))
    print("Mem<->ICache:")
    print("  ", s(mem_icache_resp_if))
    print("DCache<->Mem:")
    print("  ", s(dcache_mem_req_if))
    print("Mem<->DCache:")
    print("  ", s(mem_dcache_resp_if))
    print("ICache<->Decode:")
    print("  ", s(icache_decode_if))
    print("Decode<->Issue:")
    print("  ", s(decode_issue_if))
    print("Lsu<->DCache:")
    print("  ", s(lsu_dcache_if))
    print("DCache<->Lsu:")
    print("  ", s(dcache_lsu_if))

def call_stages(debug=False):
    
    print("\n")
    
    if(debug):
        dump_latches()

