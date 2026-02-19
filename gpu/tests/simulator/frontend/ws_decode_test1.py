from __future__ import annotations
import sys
from pathlib import Path

gpu_sim_root = Path(__file__).resolve().parents[3]
sys.path.append(str(gpu_sim_root))

from simulator.src.latch_forward_stage import LatchIF, Instruction, ForwardingIF, Stage, DecodeType
from gpu.common.custom_enums_multi import Instr_Type, R_Op, I_Op, F_Op, S_Op, B_Op, U_Op, J_Op, P_Op, H_Op
from common.custom_enums import Op
from simulator.src.scheduler.scheduler import SchedulerStage
from simulator.src.mem.icache_stage import ICacheStage
from simulator.src.mem.mem_controller import MemController
from simulator.src.mem.Memory import Mem
from simulator.src.decode.decode_class import DecodeStage
from simulator.src.decode.predicate_reg_file import PredicateRegFile
from simulator.src.latch_forward_stage import *
from datetime import datetime
from typing import Iterable, Any


def dump_array_to_timestamped_file(
    out_dir: str | Path,
    arr: Iterable[Any],
    prefix: str = "dump",
    ext: str = "txt",
    sep: str = "\n",
    include_index: bool = True,
) -> Path:
    """
    Creates out_dir if needed, writes arr to a timestamped file, returns the Path.
    Filename format: {prefix}_YYYY-MM-DD_HH-MM-SS.{ext}
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{prefix}_{ts}.{ext.lstrip('.')}"
    out_path = out_dir / filename

    with out_path.open("w", encoding="utf-8") as f:
        for i, x in enumerate(arr):
            line = f"{i}: {x}" if include_index else str(x)
            f.write(line + sep)

    return out_path

START_PC = 0x1000
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
    input_file="/home/asicfab/a/ee/cardinal/gpu/tests/simulator/frontend/ws_decode_test_binaries/no_eop.bin",
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
                    "block_size": 4, 
                    "associativity": 1},
    forward_ifs_write= {"ICache_Scheduler": icache_scheduler_fwif},
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
    print("Decode->Issue:")
    print("  ", s(decode_issue_if))

def call_stages(debug, filler_is_sched, filler_de_sched, all_instructions):
    # compute order is called in reverse: 
    # this is wrt. to cycle order: 0
    # 1) ICache taking a response back from MemController for -2 cycle
    # 2) MemController servicing requests from ICache for -1 cycle
    # 3) ICache issuing new requests to MemController for 0 cycle
    # 4) Warp Scheduler fetching instructions from ICache for 1 cycle
    # 5) TBS is going BS for t > 1 cycle

    # step #1: initiate computes to pass through dummy instructions
    # until we reach the first real fetch from TBS

    # dummy issue stage pop
    if (debug):
        dump_latches()

    updated_instruction = None
    if decode_issue_if.valid:
        updated_instruction = decode_issue_if.pop()

    if updated_instruction is None:
        print("[Issue] Did not receive any valid instruction in this cycle.")
    else:
        print(f"[Issue] Received {updated_instruction}")

        pkt = updated_instruction.packet
        word_le = int.from_bytes(pkt.bytes, "little")   # canonical 32-bit instruction word
        print(f"[Issue] packet bytes: {pkt.bytes.hex(' ')}  word(le)=0x{word_le:08x}  bits={word_le:032b}")

        all_instructions.append([updated_instruction.warp_group_id, updated_instruction.warp_id, pkt])

    if (debug): 
        dump_latches()

    decode_stage.compute()

    if (debug):
        dump_latches()

    memc.compute() # MemController servicing ICache req
    if (debug):
        dump_latches()

    icache_stage.compute() # ICache issuing new MemReq
    if (debug):
        dump_latches()

    if(issue_scheduler_fwif.payload is None):
        issue_scheduler_fwif.push(filler_is_sched)
        print(f"[TB] REPLACED ISSUE FWIF {issue_scheduler_fwif.payload}")
    
    if(decode_scheduler_fwif.payload is None):
        decode_scheduler_fwif.push(filler_de_sched)
        print(f"[TB] REPLACED DECODE FWIF {decode_scheduler_fwif.payload.get(type)}")
    
    inst = scheduler_stage.compute() # Scheduler fetching from ICache
    if (debug):
        dump_latches()
    
def cycle(num_cycles, filler_is_sched, filler_de_sched, all_instructions):
    for i in range(num_cycles):
        print(f"\nCycle #{i}\n")
        # simulate signals from issue
        call_stages(False, filler_is_sched, filler_de_sched, all_instructions)

def test_fetch(LAT=2, START_PC=0x1000, WARP_COUNT=6, num_cycles = 10):
    print("Scheduler to ICacheStage Requests Test\n")

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
    filler_decode_scheduler = {"type": DecodeType.MOP, "warp_id":0, "pc": 0}
    filler_issue_scheduler = [0] * scheduler_stage.num_groups
    icache_scheduler_fwif.payload = None
    decode_scheduler_fwif.push(filler_decode_scheduler)
    issue_scheduler_fwif.push(filler_issue_scheduler)
    branch_scheduler_fwif.payload = None
    writeback_scheduler_fwif.payload = None

    # setup some bullshit at the beginning for the latches 
    # this is initializing the latches for ONE cycle.

    tbs_ws_if.push({"warp_id": warp_id, 
                    "pc": START_PC + warp_id * 4})
    
    all_instructions = [] # list to hold the instructions decoded
    cycle(num_cycles, filler_issue_scheduler, filler_decode_scheduler, all_instructions)
    dump_array_to_timestamped_file("./test_log", all_instructions, prefix="test1_dump")

    


if __name__ == "__main__":
    test_fetch()

